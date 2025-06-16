import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import httpx
import os
import uuid
import json
import base64
from newsapi import NewsApiClient
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI
from runware import Runware, IImageInference
from core.video_service import VideoService
from fastapi.responses import FileResponse

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI application
app = FastAPI()

# Initialize global OpenAI client with API key from environment
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global variables to store the latest news article and AI-generated script response
latest_article = None
latest_ai_response = None

def create_task_response(requestId: str, task: str, status: str, message: str = "") -> str:
    """
    Generate a standardized JSON response for task status updates.
    
    Args:
        requestId (str): Unique identifier for the request.
        task (str): Task identifier (e.g., "1", "2", "Completed").
        status (str): Status of the task ("Success" or "Error").
        message (str): Optional message with details or error information.
    
    Returns:
        str: JSON string of the response.
    """
    response = {"RequestId": requestId, "Task": task, "Status": status, "Message": message}
    return json.dumps(response)

async def fetch_news_article(country: str, category: str, query: str, request_id: str):
    """
    Fetch a news article from NewsAPI based on country, category, and optional query.
    
    Args:
        country (str): Country code for news (e.g., "us").
        category (str): News category (e.g., "business").
        query (str): Optional search term for news.
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response indicating success or error.
    """
    # Retrieve NewsAPI key from environment
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        yield create_task_response(request_id, "1", "Error", "NEWS_API_KEY not set in environment.")
        return
    
    # Initialize NewsAPI client
    newsapi = NewsApiClient(api_key=api_key)
    
    # Build query parameters
    kwargs = {
        "country": country,
        "category": category,
        "page_size": 5
    }
    if query:
        kwargs["q"] = query
    
    try:
        # Fetch top headlines in a separate thread to avoid blocking
        news_json = await asyncio.to_thread(newsapi.get_top_headlines, **kwargs)
    except Exception as e:
        news_json = {"error": str(e)}
    
    # Find the first article with required fields (title, description, content)
    valid_article = None
    if "articles" in news_json and isinstance(news_json["articles"], list):
        for article in news_json["articles"]:
            if article.get("title") and article.get("description") and article.get("content"):
                valid_article = article
                break
    
    if valid_article:
        global latest_article
        latest_article = valid_article
        msg = (f"Fetched news: Title: {valid_article['title']}, "
               f"Description: {valid_article['description']}, Content: {valid_article['content']}")
        yield create_task_response(request_id, "1", "Success", msg)
    else:
        yield create_task_response(request_id, "1", "Error", "No valid news article found with all required fields.")

async def generate_news_script(request_id: str):
    global latest_article, latest_ai_response
    if latest_article is None:
        yield create_task_response(request_id, "2", "Error", "No news article data available.")
        return
    
    # Extract news article details
    news_title = latest_article.get("title", "No Title")
    news_description = latest_article.get("description", "No Description")
    news_content = latest_article.get("content", "")
    
    # Construct prompt for GPT-4 to generate a 10-scene script
    prompt = f'''
            Act as a viral content strategist and news scriptwriter for vertical video platforms like YouTube Shorts, Instagram Reels, TikTok, and Snapchat.
            Your task is to break down the following news story into a short-form, highly engaging 2-minute narration targeted at college students and young professionals (ages 18–30).
            Tone: Witty, informative, and lightly meme-style — like a confident, sarcastic best friend who knows her facts and isn’t afraid to drop a punchline.
            Voice: Female with strong personality. Include rhetorical hooks, Gen Z-friendly humor, and clever metaphors. Feel free to reference pop culture, TikTok trends, or modern slang in a tasteful way.
            News Style: Cover all types — breaking news, trending topics, weird facts, tech, social issues, etc.
            Output the response as JSON in this exact structure:
                {{
                "1": {{ "script": "Scene 1 script here", "imagePrompt": "Scene 1 image description", "effect": "pan_left", "duration": 15 }},
                "2": {{ "script": "Scene 2 script here", "imagePrompt": "Scene 2 image description", "effect": "zoom_in", "duration": 12 }},
                ...,
                "metadata": {{ "title": "Insert catchy video title based on the news", "description": "Insert a short YouTube-style description summarizing the story in 1–2 lines with hashtags if relevant" 
                }}
                }}
            Each scene should:
                •	Be 10–15 seconds long
                •	Push the story forward in a fun, engaging way
                •	Use visual metaphors or animated whiteboard/doodle-style scenes
                •	Include motion effects like zoom_in, pan_right, fade_in, wobble, etc.

            End the final scene with a strong call to action, like:
            “If you liked this, hit follow — you deserve better news.”
            Begin with this news story:
            {news_content}
    '''
    
    try:
        # Call OpenAI API in a separate thread for non-blocking execution
        response = await asyncio.to_thread(
            lambda: openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
        )
        ai_output = response.choices[0].message.content
        try:
            # Validate the AI response by parsing it as JSON
            json.loads(ai_output)
            latest_ai_response = ai_output
            yield create_task_response(request_id, "2", "Success")
        except Exception as parse_error:
            yield create_task_response(request_id, "2", "Error", f"JSON parsing error: {str(parse_error)}")
    except Exception as e:
        yield create_task_response(request_id, "2", "Error", str(e))

async def serialize_script_response(request_id: str):
    """
    Serialize and validate the AI-generated script response, adding scene IDs and request ID.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response indicating success, error, or serialized data.
    """
    global latest_ai_response
    if latest_ai_response is None:
        yield create_task_response(request_id, "2a", "Error", "No AI response available to serialize.")
        return
    
    try:
        # Parse AI response JSON
        ai_data = json.loads(latest_ai_response)
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
        
        for scene_number in map(str, range(1, 11)):
            if scene_number not in ai_data:
                error_messages.append(f"Missing scene {scene_number}.")
            else:
                scene = ai_data[scene_number]
                if not isinstance(scene, dict):
                    error_messages.append(f"Scene {scene_number} is not a dictionary.")
                else:
                    if "script" not in scene:
                        error_messages.append(f"Missing 'script' in scene {scene_number}.")
                    if "imagePrompt" not in scene:
                        error_messages.append(f"Missing 'imagePrompt' in scene {scene_number}.")
                    if "scene_id" not in scene:
                        error_messages.append(f"Missing 'scene_id' in scene {scene_number}.")
        
        if error_messages:
            yield create_task_response(request_id, "2a", "Error", "; ".join(error_messages))
        else:
            yield create_task_response(request_id, "2a", "Success")
        
        # Serialize validated JSON and yield
        serialized = json.dumps(ai_data, indent=2)
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

async def convert_scripts_to_audio(request_id: str):
    """
    Convert each scene's script to an audio file using OpenAI TTS.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response for each scene's audio generation status.
    """
    global latest_ai_response
    if latest_ai_response is None:
        yield create_task_response(request_id, "3", "Error", "No AI response available for audio generation.")
        return
    
    try:
        # Parse AI response JSON
        ai_data = json.loads(latest_ai_response)
    except Exception as e:
        yield create_task_response(request_id, "3", "Error", f"Error parsing AI response: {str(e)}")
        return
    
    messages = []
    for scene_number in map(str, range(1, 11)):
        scene = ai_data.get(scene_number)
        if scene and "script" in scene:
            script_text = scene["script"]
            try:
                # Generate audio file for the scene
                file_path = await generate_audio_file(request_id, script_text, scene_number)
                ai_data[scene_number]["audioPath"] = file_path
                messages.append(create_task_response(request_id, "3", "Success", f"Audio file generated for scene {scene_number}: {file_path}"))
            except Exception as gen_err:
                messages.append(create_task_response(request_id, "3", "Error", f"Error generating audio for scene {scene_number}: {str(gen_err)}"))
        else:
            messages.append(create_task_response(request_id, "3", "Error", f"Scene {scene_number} missing script data."))
    
    # Update global AI response with audio paths
    latest_ai_response = json.dumps(ai_data)
    
    for m in messages:
        yield m

async def generate_scene_images(request_id: str):
    """
    Generate images for each scene using Runware's image inference API.
    
    Args:
        request_id (str): Unique identifier for the request.
    
    Yields:
        str: JSON response for each scene's image generation status.
    """
    global latest_ai_response
    if latest_ai_response is None:
        yield create_task_response(request_id, "4", "Error", "No AI response available for image generation.")
        return
    
    try:
        # Parse AI response JSON
        ai_data = json.loads(latest_ai_response)
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
    for scene_number in map(str, range(1, 11)):
        scene = ai_data.get(scene_number)
        if scene and "imagePrompt" in scene:
            image_prompt = scene["imagePrompt"]
            try:
                # Create image inference request
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
                    ai_data[scene_number]["imageUrl"] = image_url
                    messages.append(create_task_response(request_id, "4", "Success", f"Image generated for scene {scene_number}: {image_url}"))
                else:
                    messages.append(create_task_response(request_id, "4", "Error", f"No image generated for scene {scene_number}."))
            except Exception as e:
                messages.append(create_task_response(request_id, "4", "Error", f"Error generating image for scene {scene_number}: {str(e)}"))
        else:
            messages.append(create_task_response(request_id, "4", "Error", f"Scene {scene_number} missing imagePrompt."))
    
    # Update global AI response with image URLs
    latest_ai_response = json.dumps(ai_data)
    
    for m in messages:
        yield m

async def stitch_video_from_scenes(request_id: str):
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
        json.dump(json.loads(latest_ai_response), file, indent=2)
    
    # Generate video
    await asyncio.to_thread(service.generate, filename, f"data/{request_id}/final_video.mp4")
    yield create_task_response(request_id, "5", "Success", f"Video generated: data/{request_id}/final_video.mp4")

async def pipeline_tasks(country: str, category: str, query: str):
    """
    Orchestrate the video generation pipeline, executing tasks sequentially.
    
    Args:
        country (str): Country code for news.
        category (str): News category.
        query (str): Optional search term for news.
    
    Yields:
        str: JSON response for each task's status.
    """
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    yield create_task_response(request_id, "0", "Success", f"Request ID: {request_id}")
    
    # Execute pipeline tasks
    async for message in fetch_news_article(country, category, query, request_id):
        yield message
    async for message in generate_news_script(request_id):
        yield message
    async for message in serialize_script_response(request_id):
        yield message
    async for message in convert_scripts_to_audio(request_id):
        yield message
    async for message in generate_scene_images(request_id):
        yield message
    async for message in stitch_video_from_scenes(request_id):
        yield message
    yield create_task_response(request_id, "Completed", "Success", f"Request ID: {request_id}")

@app.get("/stream")
async def stream_endpoint(country: str = "us", category: str = "business", query: str = ""):
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
        async for message in pipeline_tasks(country, category, query):
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