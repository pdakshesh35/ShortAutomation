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

# Import Runware client interfaces.
from runware import Runware, IImageInference

# At the top of your module, import the editor:
from video_service import VideoService
from fastapi.responses import FileResponse
import os

load_dotenv()
app = FastAPI()

# Create a global OpenAI client instance.
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Helper function to generate standardized task response messages.
def create_task_response(requestId: str, task: str, status: str, message: str = "") -> str:
    response = {"RequestId": requestId, "Task": task, "Status": status, "Message": message}
    return json.dumps(response)

latest_article = None
latest_ai_response = None

async def task1_get_news(country: str, category: str, query: str, request_id: str):
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        yield create_task_response(request_id, "1", "Error", "NEWS_API_KEY not set in environment.")
        return
    newsapi = NewsApiClient(api_key=api_key)
    # Build parameters dynamically.
    kwargs = {
        "country": country,
        "category": category,
        "page_size": 5
    }
    if query:
        kwargs["q"] = query
    try:
        # Run the synchronous API call in a separate thread.
        news_json = await asyncio.to_thread(newsapi.get_top_headlines, **kwargs)
    except Exception as e:
        news_json = {"error": str(e)}
    
    # Validation: find the very first article with title, description, and content.
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

async def task2_convert_news_to_script(request_id: str):
    global latest_article, latest_ai_response
    if latest_article is None:
        yield create_task_response(request_id, "2", "Error", "No news article data available.")
        return
    news_title = latest_article.get("title", "No Title")
    news_description = latest_article.get("description", "No Description")
    news_content = latest_article.get("content", "")
    
    # Construct the prompt using the news details.
    prompt = f'''Write a prompt which generate 2 mint youtube short script which narrate news in 10 scenes, where first scene will be the opening, and last scene should mention to subscribe for daily news. The purpose of this news narration is we want to narrate news in cool engaging way so that youth also look for our channel for news. Also most of the times we hear news we dont know how its gonna impact or relate to us, so we want to solve that problem

Instruction for Image Prompts : "Imagine a visually dynamic scene filled with vibrant colors and fluid shapes that evoke emotion and energy without any textual elements. The image should display an abstract interplay of light, shadows, and organic forms that suggest movement and narrative depth, using visual cues like radiant gradients, swirling patterns, and symbolic silhouettes to tell a story purely through imagery, completely free of any words or lettering."

News Content : {news_content}
Output Format:
Return the final result in the following JSON structure:
{{
  "1": {{ "script": "Your Scene 1 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 1 here" }},
  "2": {{ "script": "Your Scene 2 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 2 here" }},
  "3": {{ "script": "Your Scene 3 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 3 here" }},
  "4": {{ "script": "Your Scene 4 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 4 here" }},
  "5": {{ "script": "Your Scene 5 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 5 here" }},
  "6": {{ "script": "Your Scene 6 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 6 here" }},
  "7": {{ "script": "Your Scene 7 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 7 here" }},
  "8": {{ "script": "Your Scene 8 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 8 here" }},
  "9": {{ "script": "Your Scene 9 script here", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 9 here" }},
  "10": {{ "script": "Your Scene 10 script here, including a strong call-to-action to subscribe for more content", "imagePrompt": "Your detailed Videoscribe image prompt for Scene 10 here" }},
  "metadata": {{ "title": "{news_title}", "description": "{news_description}" }}
}}'''
    
    try:
         # Wrap the synchronous OpenAI chat completion call in a thread.
         response = await asyncio.to_thread(
            lambda: openai_client.chat.completions.create(
                model="gpt-4",  # or "gpt-4.1" if required by your reference.
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
         )
         ai_output = response.choices[0].message.content
         try:
             # Validate the AI response by trying to parse as JSON.
             json.loads(ai_output)
             latest_ai_response = ai_output  # Record output globally if valid.
             validation_message = create_task_response(request_id, "2", "Success")
             yield validation_message
         except Exception as parse_error:
             validation_message = create_task_response(request_id, "2", "Error", f"JSON parsing error: {str(parse_error)}")
             yield validation_message
    except Exception as e:
         error_message = create_task_response(request_id, "2", "Error", str(e))
         yield error_message

async def task2a_serialize_response(request_id: str):
    global latest_ai_response
    if latest_ai_response is None:
        yield create_task_response(request_id, "2a", "Error", "No AI response available to serialize.")
        return
    try:
        ai_data = json.loads(latest_ai_response)
        ai_data["request_id"] = request_id
        for key in ai_data:
            if key.isdigit() and isinstance(ai_data[key], dict):
                ai_data[key]["scene_id"] = str(uuid.uuid4())
        
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
            validation_message = create_task_response(request_id, "2a", "Error", "; ".join(error_messages))
            yield validation_message
        else:
            validation_message = create_task_response(request_id, "2a", "Success")
            yield validation_message
        
        serialized = json.dumps(ai_data, indent=2)
        yield create_task_response(request_id, "2a", "Success", serialized)
    except Exception as e:
         error_message = create_task_response(request_id, "2a", "Error", str(e))
         yield error_message

# Updated generate_audio_file using the new OpenAI client.
async def generate_audio_file(request_id: str, text: str, scene_number: str) -> str:
    os.makedirs(f"data/{request_id}", exist_ok=True)
    file_path = os.path.join(f"data/{request_id}", f"audio-{scene_number}.mp3")
    try:
        # Call the asynchronous audio creation endpoint using the new client.
        response = openai_client.audio.speech.create(
            model="tts-1",             # Use the chosen TTS model.
            voice="nova",             # Choose the voice.
            input=text,                # The text to convert.
        )
       
        response.stream_to_file(file_path)
    except Exception as e:
        raise e
    return file_path

async def task3_script_to_audio(request_id: str):
    global latest_ai_response
    if latest_ai_response is None:
        yield create_task_response(request_id, "3", "Error", "No AI response available for audio generation.")
        return
    try:
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
                file_path = await generate_audio_file(request_id, script_text, scene_number)
                
                # Add audioPath to scene JSON
                ai_data[scene_number]["audioPath"] = file_path
                
                msg = f"Audio file generated for scene {scene_number}: {file_path}"
                messages.append(create_task_response(request_id, "3", "Success", msg))
            except Exception as gen_err:
                msg = f"Error generating audio for scene {scene_number}: {str(gen_err)}"
                messages.append(create_task_response(request_id, "3", "Error", msg))
        else:
            msg = f"Scene {scene_number} missing script data."
            messages.append(create_task_response(request_id, "3", "Error", msg))
        
    # Update global AI response JSON with audio paths
    latest_ai_response = json.dumps(ai_data)
    
    for m in messages:
        yield m

async def task4_create_images(request_id: str):
    global latest_ai_response
    if latest_ai_response is None:
        yield create_task_response(request_id, "4", "Error", "No AI response available for image generation.")
        return
    try:
        ai_data = json.loads(latest_ai_response)
    except Exception as e:
        yield create_task_response(request_id, "4", "Error", f"Error parsing AI response: {str(e)}")
        return
    
    try:
        # Initialize Runware client and connect.
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
                request_image = IImageInference(
                    positivePrompt=image_prompt,
                    taskUUID=str(uuid.uuid4()),
                    model="runware:100@1",  # Use your desired model.
                    numberResults=1,
                    height=2048,
                    width=1152
                )
                images = await runware_client.imageInference(requestImage=request_image)
                if images and len(images) > 0:
                    image_url = images[0].imageURL
                    
                    # Add imageUrl to scene JSON
                    ai_data[scene_number]["imageUrl"] = image_url
                    
                    msg = f"Image generated for scene {scene_number}: {image_url}"
                    messages.append(create_task_response(request_id, "4", "Success", msg))
                else:
                    msg = f"No image generated for scene {scene_number}."
                    messages.append(create_task_response(request_id, "4", "Error", msg))
            except Exception as e:
                msg = f"Error generating image for scene {scene_number}: {str(e)}"
                messages.append(create_task_response(request_id, "4", "Error", msg))
        else:
            msg = f"Scene {scene_number} missing imagePrompt."
            messages.append(create_task_response(request_id, "4", "Error", msg))
    
    # Update global AI response JSON with image URLs
    latest_ai_response = json.dumps(ai_data)
    
    for m in messages:
        yield m

async def task5_stitch_video(request_id: str):
    service = VideoService(width=1080, height=1920)
    filename = f"data/{request_id}/payload.json"
    with open(filename, 'w') as file:
        json.dump(json.loads(latest_ai_response), file, indent=2)
    service.generate(filename, f"data/{request_id}/final_video.mp4")
    yield create_task_response(request_id, "5", "Success", f"Video generated: data/{request_id}/final_video.mp4")

async def pipeline_tasks(country: str, category: str, query: str):
    request_id = str(uuid.uuid4())
    yield create_task_response(request_id, "0", "Success", f"Request ID: {request_id}")
    async for message in task1_get_news(country, category, query, request_id):
        yield message
    async for message in task2_convert_news_to_script(request_id):
        yield message
    async for message in task2a_serialize_response(request_id):
        yield message
    async for message in task3_script_to_audio(request_id):
        yield message
    async for message in task4_create_images(request_id):
        yield message
    async for message in task5_stitch_video(request_id):
        yield message
    yield create_task_response(request_id, "Completed", "Success", f"Request ID: {request_id}")

@app.get("/stream")
async def stream_endpoint(country: str = "us", category: str = "business", query: str = ""):
    async def event_generator():
        async for message in pipeline_tasks(country, category, query):
            yield f"data: {message}\n\n"
            # Check for the "Completed" task to break the loop
            if '"Task":"Completed"' in message:
                yield "data: {}\n\n"  # Send an empty event to signal end
                break
        # Ensure no further yields after completion
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
    Test endpoint that generates a video from payload.json and returns the MP4 file.
    """
    service = VideoService(width=1152, height=2048)
    input_json = "data/f851c750-b4a6-45fa-b23d-5c268e738e95/payload.json"
    os.makedirs("data", exist_ok=True)
    output_video = "data/test_video.mp4"
    service.generate(input_json, output_video)
    return FileResponse(output_video, media_type="video/mp4", filename="test_video.mp4")