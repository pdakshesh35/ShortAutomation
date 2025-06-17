import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import os
import uuid
import json
from dotenv import load_dotenv
from openai import OpenAI
from runware import Runware, IImageInference
from core.video_service import VideoService
from fastapi.responses import FileResponse
from niches import get_handler
from utils import create_task_response

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI application
app = FastAPI()

# Initialize global OpenAI client with API key from environment
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def serialize_script_response(handler, request_id: str):
    """
    Serialize and validate the AI-generated script response, adding scene IDs and request ID.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response indicating success, error, or serialized data.
    """
    if handler.ai_response is None:
        yield create_task_response(request_id, "2a", "Error", "No AI response available to serialize.")
        return

    try:
        # Parse AI response JSON
        ai_data = json.loads(handler.ai_response)
        ai_data["request_id"] = request_id
        
        # Add unique scene IDs to each scene
        for key in ai_data:
            if key.isdigit() and isinstance(ai_data[key], dict):
                ai_data[key]["scene_id"] = str(uuid.uuid4())
        
        # Validate JSON structure
        error_messages = []
        if "metadata" not in ai_data:
            error_messages.append("Missing 'metadata' key.")
        else:
            if "title" not in ai_data["metadata"]:
                error_messages.append("Missing 'title' in metadata.")
            if "description" not in ai_data["metadata"]:
                error_messages.append("Missing 'description' in metadata.")
        
        scene_numbers = sorted(int(k) for k in ai_data.keys() if k.isdigit())
        if not scene_numbers:
            error_messages.append("No scenes found in AI response.")
        for num in scene_numbers:
            key = str(num)
            scene = ai_data.get(key)
            if not isinstance(scene, dict):
                error_messages.append(f"Scene {key} is not a dictionary.")
                continue
            if "script" not in scene:
                error_messages.append(f"Missing 'script' in scene {key}.")
            if "imagePrompt" not in scene:
                error_messages.append(f"Missing 'imagePrompt' in scene {key}.")
            if "scene_id" not in scene:
                error_messages.append(f"Missing 'scene_id' in scene {key}.")
        
        if error_messages:
            yield create_task_response(request_id, "2a", "Error", "; ".join(error_messages))
        else:
            yield create_task_response(request_id, "2a", "Success")
        
        # Serialize validated JSON and yield
        serialized = json.dumps(ai_data, indent=2)
        handler.ai_response = serialized
        yield create_task_response(request_id, "2a", "Success", serialized)
    except Exception as e:
        yield create_task_response(request_id, "2a", "Error", str(e))

async def generate_audio_file(request_id: str, text: str, scene_number: str) -> str:
    """
    Generate an audio file from text using OpenAI's TTS API and save it to disk.
    
    Args:
        request_id (str): Unique identifier for the request.
        text (str): Text to convert to audio.
        scene_number (str): Scene number for naming the audio file.
    
    Returns:
        str: Path to the generated audio file.
    
    Raises:
        Exception: If audio generation or file saving fails.
    """
    # Create directory for request-specific data
    os.makedirs(f"data/{request_id}", exist_ok=True)
    file_path = os.path.join(f"data/{request_id}", f"audio-{scene_number}.mp3")
    
    try:
        # Generate audio using OpenAI TTS in a background thread
        response = await asyncio.to_thread(
            lambda: openai_client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
            )
        )
        await asyncio.to_thread(response.stream_to_file, file_path)
    except Exception as e:
        raise e
    return file_path

async def convert_scripts_to_audio(handler, request_id: str):
    """
    Convert each scene's script to an audio file using OpenAI TTS.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response for each scene's audio generation status.
    """
    if handler.ai_response is None:
        yield create_task_response(request_id, "3", "Error", "No AI response available for audio generation.")
        return

    try:
        # Parse AI response JSON
        ai_data = json.loads(handler.ai_response)
    except Exception as e:
        yield create_task_response(request_id, "3", "Error", f"Error parsing AI response: {str(e)}")
        return
    
    messages = []
    scene_numbers = sorted(int(k) for k in ai_data.keys() if k.isdigit())
    for num in scene_numbers:
        key = str(num)
        scene = ai_data.get(key)
        if scene and "script" in scene:
            script_text = scene["script"]
            try:
                file_path = await generate_audio_file(request_id, script_text, key)
                ai_data[key]["audioPath"] = file_path
                messages.append(create_task_response(request_id, "3", "Success", f"Audio file generated for scene {key}: {file_path}"))
            except Exception as gen_err:
                messages.append(create_task_response(request_id, "3", "Error", f"Error generating audio for scene {key}: {str(gen_err)}"))
        else:
            messages.append(create_task_response(request_id, "3", "Error", f"Scene {key} missing script data."))
    
    # Update global AI response with audio paths
    handler.ai_response = json.dumps(ai_data)
    
    for m in messages:
        yield m

async def generate_scene_images(handler, request_id: str):
    """
    Generate images for each scene using Runware's image inference API.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response for each scene's image generation status.
    """
    if handler.ai_response is None:
        yield create_task_response(request_id, "4", "Error", "No AI response available for image generation.")
        return
    
    try:
        # Parse AI response JSON
        ai_data = json.loads(handler.ai_response)
    except Exception as e:
        yield create_task_response(request_id, "4", "Error", f"Error parsing AI response: {str(e)}")
        return
    
    try:
        # Initialize and connect to Runware client
        runware_client = Runware(api_key=os.getenv("RUNWARE_API_KEY"))
        await runware_client.connect()
    except Exception as e:
        yield create_task_response(request_id, "4", "Error", f"Error connecting to Runware: {str(e)}")
        return

    messages = []
    scene_numbers = sorted(int(k) for k in ai_data.keys() if k.isdigit())
    for num in scene_numbers:
        key = str(num)
        scene = ai_data.get(key)
        if scene and "imagePrompt" in scene:
            image_prompt = scene["imagePrompt"]
            try:
                request_image = IImageInference(
                    positivePrompt=image_prompt,
                    taskUUID=str(uuid.uuid4()),
                    model="runware:100@1",
                    numberResults=1,
                    height=2048,
                    width=1152
                )
                images = await runware_client.imageInference(requestImage=request_image)
                if images and len(images) > 0:
                    image_url = images[0].imageURL
                    ai_data[key]["imageUrl"] = image_url
                    messages.append(create_task_response(request_id, "4", "Success", f"Image generated for scene {key}: {image_url}"))
                else:
                    messages.append(create_task_response(request_id, "4", "Error", f"No image generated for scene {key}."))
            except Exception as e:
                messages.append(create_task_response(request_id, "4", "Error", f"Error generating image for scene {key}: {str(e)}"))
        else:
            messages.append(create_task_response(request_id, "4", "Error", f"Scene {key} missing imagePrompt."))
    
    # Update global AI response with image URLs
    handler.ai_response = json.dumps(ai_data)
    
    for m in messages:
        yield m

async def stitch_video_from_scenes(handler, request_id: str):
    """
    Stitch scenes into a final video using VideoService, combining audio, images, and subtitles.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response indicating video generation status.
    """
    # Initialize VideoService with 1080x1920 resolution
    service = VideoService(width=1080, height=1920)
    
    # Save AI response as JSON payload
    filename = f"data/{request_id}/payload.json"
    with open(filename, 'w') as file:
        json.dump(json.loads(handler.ai_response), file, indent=2)
    
    # Generate video
    await asyncio.to_thread(service.generate, filename, f"data/{request_id}/final_video.mp4", handler.background_music_path())
    yield create_task_response(request_id, "5", "Success", f"Video generated: data/{request_id}/final_video.mp4")

async def pipeline_tasks(niche: str, country: str, category: str, query: str):
    """
    Orchestrate the video generation pipeline, executing tasks sequentially.
    
    Args:
        country (str): Country code for news.
        category (str): News category.
        query (str): Optional search term for news.
    
    Yields:
        str: JSON response for each task's status.
    """
    handler = get_handler(niche, openai_client)
    request_id = str(uuid.uuid4())
    yield create_task_response(request_id, "0", "Success", f"Request ID: {request_id}")

    async for message in handler.fetch_content(request_id=request_id, country=country, category=category, query=query):
        yield message
    async for message in handler.generate_script(request_id):
        yield message
    async for message in serialize_script_response(handler, request_id):
        yield message
    async for message in convert_scripts_to_audio(handler, request_id):
        yield message
    async for message in generate_scene_images(handler, request_id):
        yield message
    async for message in stitch_video_from_scenes(handler, request_id):
        yield message
    yield create_task_response(request_id, "Completed", "Success", f"Request ID: {request_id}")

@app.get("/stream")
async def stream_endpoint(niche: str = "news", country: str = "us", category: str = "business", query: str = ""):
    """
    Stream the video generation pipeline as Server-Sent Events (SSE).
    
    Args:
        country (str): Country code for news (default: "us").
        category (str): News category (default: "business").
        query (str): Optional search term for news.
    
    Returns:
        StreamingResponse: SSE stream of task status updates.
    """
    async def event_generator():
        # Yield task status messages as SSE events
        async for message in pipeline_tasks(niche, country, category, query):
            yield f"data: {message}\n\n"
            # Terminate stream after "Completed" message
            if '"Task":"Completed"' in message:
                yield "data: {}\n\n"  # Signal end of stream
                break
        return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@app.get("/test-video")
def test_video():
    """
    Test endpoint to generate a video from a sample JSON payload.
    
    Returns:
        FileResponse: Generated MP4 video file.
    """
    # Initialize VideoService with 1152x2048 resolution
    service = VideoService(width=1152, height=2048)
    input_json = "data/a47bf841-39e2-4556-b414-32c6ce0682d1/payload.json"
    os.makedirs("data", exist_ok=True)
    output_video = "data/test_video.mp4"
    
    # Generate and return video
    service.generate(input_json, output_video)
    return FileResponse(output_video, media_type="video/mp4", filename="test_video.mp4")
