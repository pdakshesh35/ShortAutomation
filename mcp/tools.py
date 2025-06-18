import asyncio
import json
import os
import uuid
from runware import Runware, IImageInference
from core.video_service import VideoService
from utils import create_task_response
from . import tool
from .context import MCPContext


@tool("init_request")
async def init_request(niche: str) -> MCPContext:
    """Create a new MCP context for the given niche."""
    return MCPContext(niche)


@tool("fetch_content")
async def fetch_content(ctx: MCPContext, country: str, category: str, query: str):
    messages = []
    async for message in ctx.handler.fetch_content(
        request_id=ctx.request_id,
        country=country,
        category=category,
        query=query,
    ):
        messages.append(message)
    return messages


@tool("generate_script")
async def generate_script(ctx: MCPContext):
    messages = []
    async for message in ctx.handler.generate_script(ctx.request_id):
        messages.append(message)
    ctx.ai_response = ctx.handler.ai_response
    return messages


@tool("serialize_script")
async def serialize_script(ctx: MCPContext):
    if ctx.handler.ai_response is None:
        return [create_task_response(ctx.request_id, "2a", "Error", "No AI response available to serialize.")]

    messages = []
    try:
        ai_data = json.loads(ctx.handler.ai_response)
        ai_data["request_id"] = ctx.request_id
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
            messages.append(create_task_response(ctx.request_id, "2a", "Error", "; ".join(error_messages)))
        else:
            messages.append(create_task_response(ctx.request_id, "2a", "Success"))

        serialized = json.dumps(ai_data, indent=2)
        ctx.handler.ai_response = serialized
        ctx.ai_response = serialized
        messages.append(create_task_response(ctx.request_id, "2a", "Success", serialized))
    except Exception as e:
        messages.append(create_task_response(ctx.request_id, "2a", "Error", str(e)))
    return messages


async def _generate_audio_file(ctx: MCPContext, text: str, scene_number: str) -> str:
    os.makedirs(f"data/{ctx.request_id}", exist_ok=True)
    file_path = os.path.join(f"data/{ctx.request_id}", f"audio-{scene_number}.mp3")
    response = await asyncio.to_thread(
        lambda: ctx.openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
        )
    )
    await asyncio.to_thread(response.stream_to_file, file_path)
    return file_path


@tool("convert_scripts_to_audio")
async def convert_scripts_to_audio(ctx: MCPContext):
    if ctx.handler.ai_response is None:
        return [create_task_response(ctx.request_id, "3", "Error", "No AI response available for audio generation.")]

    try:
        ai_data = json.loads(ctx.handler.ai_response)
    except Exception as e:
        return [create_task_response(ctx.request_id, "3", "Error", f"Error parsing AI response: {str(e)}")]

    messages = []
    scene_numbers = sorted(int(k) for k in ai_data.keys() if k.isdigit())
    for num in scene_numbers:
        key = str(num)
        scene = ai_data.get(key)
        if scene and "script" in scene:
            script_text = scene["script"]
            try:
                file_path = await _generate_audio_file(ctx, script_text, key)
                ai_data[key]["audioPath"] = file_path
                messages.append(create_task_response(ctx.request_id, "3", "Success", f"Audio file generated for scene {key}: {file_path}"))
            except Exception as gen_err:
                messages.append(create_task_response(ctx.request_id, "3", "Error", f"Error generating audio for scene {key}: {str(gen_err)}"))
        else:
            messages.append(create_task_response(ctx.request_id, "3", "Error", f"Scene {key} missing script data."))

    ctx.handler.ai_response = json.dumps(ai_data)
    ctx.ai_response = ctx.handler.ai_response
    return messages


@tool("generate_scene_images")
async def generate_scene_images(ctx: MCPContext):
    if ctx.handler.ai_response is None:
        return [create_task_response(ctx.request_id, "4", "Error", "No AI response available for image generation.")]

    try:
        ai_data = json.loads(ctx.handler.ai_response)
    except Exception as e:
        return [create_task_response(ctx.request_id, "4", "Error", f"Error parsing AI response: {str(e)}")]

    try:
        runware_client = Runware(api_key=os.getenv("RUNWARE_API_KEY"))
        await runware_client.connect()
    except Exception as e:
        return [create_task_response(ctx.request_id, "4", "Error", f"Error connecting to Runware: {str(e)}")]

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
                    width=1152,
                )
                images = await runware_client.imageInference(requestImage=request_image)
                if images and len(images) > 0:
                    image_url = images[0].imageURL
                    ai_data[key]["imageUrl"] = image_url
                    messages.append(create_task_response(ctx.request_id, "4", "Success", f"Image generated for scene {key}: {image_url}"))
                else:
                    messages.append(create_task_response(ctx.request_id, "4", "Error", f"No image generated for scene {key}."))
            except Exception as e:
                messages.append(create_task_response(ctx.request_id, "4", "Error", f"Error generating image for scene {key}: {str(e)}"))
        else:
            messages.append(create_task_response(ctx.request_id, "4", "Error", f"Scene {key} missing imagePrompt."))

    ctx.handler.ai_response = json.dumps(ai_data)
    ctx.ai_response = ctx.handler.ai_response
    return messages


@tool("stitch_video")
async def stitch_video(ctx: MCPContext):
    service = VideoService(width=1080, height=1920)
    filename = f"data/{ctx.request_id}/payload.json"
    with open(filename, "w") as file:
        json.dump(json.loads(ctx.handler.ai_response), file, indent=2)

    await asyncio.to_thread(
        service.generate,
        filename,
        f"data/{ctx.request_id}/final_video.mp4",
        ctx.background_music_path(),
    )
    return [create_task_response(ctx.request_id, "5", "Success", f"Video generated: data/{ctx.request_id}/final_video.mp4")]
