from __future__ import annotations
import asyncio
import json
import os
import uuid
from openai import OpenAI
from runware import Runware, IImageInference
from newsapi import NewsApiClient
from mcp.server.fastmcp import FastMCP
from core.video_service import VideoService
from niches.base import PROMPT_STRUCTURE_INSTRUCTIONS

mcp = FastMCP("Short Automation")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@mcp.resource(
    "news://article",
    description="Fetch a news article from NewsAPI based on country, category, and optional search query",
)
async def fetch_news(country: str = "us", category: str = "business", query: str = "") -> dict:
    """Return a single news article as a JSON object."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise RuntimeError("NEWS_API_KEY not set")
    newsapi = NewsApiClient(api_key=api_key)
    kwargs = {"country": country, "category": category, "page_size": 5}
    if query:
        kwargs["q"] = query
    news_json = await asyncio.to_thread(newsapi.get_top_headlines, **kwargs)
    for article in news_json.get("articles", []):
        if article.get("title") and article.get("description") and article.get("content"):
            return article
    raise RuntimeError("No valid article found")


@mcp.prompt(
    "script-prompt",
    description="Prompt template that converts a raw news article into a multi-scene JSON script",
)
def news_script_prompt(article: str) -> str:
    """Build the structured prompt for script generation."""
    return (
        f"""
            Act as a viral content strategist and news scriptwriter for vertical video platforms like YouTube Shorts, Instagram Reels, TikTok, and Snapchat.
            Your task is to break down the following news story into a short-form, highly engaging 2-minute narration targeted at college students and young professionals (ages 18–30).
            Tone: Witty, informative, and lightly meme-style — like a confident, sarcastic best friend who knows her facts and isn’t afraid to drop a punchline.
            Voice: Female with strong personality. Include rhetorical hooks, Gen Z-friendly humor, and clever metaphors. Feel free to reference pop culture, TikTok trends, or modern slang in a tasteful way.
            News Style: Cover all types — breaking news, trending topics, weird facts, tech, social issues, etc.
            {PROMPT_STRUCTURE_INSTRUCTIONS}

            End the final scene with a strong call to action, like:
            “If you liked this, hit follow — you deserve better news.”
            Begin with this news story:
            {article}
        """
    )


@mcp.tool(
    description="Call OpenAI to generate a multi-scene JSON script using the provided prompt",
)
async def generate_script(prompt: str) -> str:
    """Generate a multi-scene script using OpenAI ChatGPT."""
    response = await asyncio.to_thread(
        lambda: openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
    )
    return response.choices[0].message.content


@mcp.tool(
    description="Validate and enrich the JSON script with unique scene IDs and a request ID",
)
def serialize_script(script: str) -> str:
    """Validate the script JSON and assign scene IDs."""
    ai_data = json.loads(script)
    request_id = ai_data.get("request_id") or str(uuid.uuid4())
    ai_data["request_id"] = request_id
    for key in ai_data:
        if key.isdigit() and isinstance(ai_data[key], dict):
            ai_data[key]["scene_id"] = str(uuid.uuid4())
    return json.dumps(ai_data, indent=2)


@mcp.tool(
    description="Convert each scene of the JSON script into MP3 audio using OpenAI TTS",
)
async def scripts_to_audio(script: str) -> str:
    """Convert each scene's script to audio using OpenAI TTS."""
    ai_data = json.loads(script)
    request_id = ai_data.get("request_id") or str(uuid.uuid4())
    ai_data["request_id"] = request_id
    os.makedirs(f"data/{request_id}", exist_ok=True)
    scene_numbers = sorted(int(k) for k in ai_data.keys() if k.isdigit())
    for num in scene_numbers:
        scene = ai_data[str(num)]
        text = scene.get("script", "")
        response = await asyncio.to_thread(
            lambda: openai_client.audio.speech.create(model="tts-1", voice="nova", input=text)
        )
        path = os.path.join(f"data/{request_id}", f"audio-{num}.mp3")
        await asyncio.to_thread(response.stream_to_file, path)
        scene["audioPath"] = path
    return json.dumps(ai_data, indent=2)


@mcp.tool(
    description="Generate an image for each scene using Runware's image inference API",
)
async def generate_images(script: str) -> str:
    """Generate scene images using Runware."""
    ai_data = json.loads(script)
    request_id = ai_data.get("request_id") or str(uuid.uuid4())
    ai_data["request_id"] = request_id
    runware_client = Runware(api_key=os.getenv("RUNWARE_API_KEY"))
    await runware_client.connect()
    scene_numbers = sorted(int(k) for k in ai_data.keys() if k.isdigit())
    for num in scene_numbers:
        scene = ai_data[str(num)]
        prompt = scene.get("imagePrompt", "")
        request_image = IImageInference(
            positivePrompt=prompt,
            taskUUID=str(uuid.uuid4()),
            model="runware:100@1",
            numberResults=1,
            height=2048,
            width=1152,
        )
        images = await runware_client.imageInference(requestImage=request_image)
        if images:
            scene["imageUrl"] = images[0].imageURL
    return json.dumps(ai_data, indent=2)


@mcp.tool(
    description="Combine images and audio for all scenes and render the final vertical video",
)
def stitch_video(script: str) -> str:
    """Stitch audio and images into a final video."""
    ai_data = json.loads(script)
    request_id = ai_data.get("request_id") or str(uuid.uuid4())
    ai_data["request_id"] = request_id
    os.makedirs(f"data/{request_id}", exist_ok=True)
    payload_file = f"data/{request_id}/payload.json"
    with open(payload_file, "w", encoding="utf-8") as f:
        json.dump(ai_data, f, indent=2)
    service = VideoService(width=1080, height=1920)
    output_path = f"data/{request_id}/final_video.mp4"
    service.generate(payload_file, output_path)
    return output_path


@mcp.tool(
    description="Complete pipeline: given a raw news article string, generate the video file path",
)
async def article_to_video(article: str) -> str:
    """Generate a video directly from a news article."""
    prompt = news_script_prompt(article)
    script = await generate_script(prompt)
    serialized = serialize_script(script)
    audio_json = await scripts_to_audio(serialized)
    images_json = await generate_images(audio_json)
    return stitch_video(images_json)


if __name__ == "__main__":
    mcp.run("sse")
