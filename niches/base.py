import asyncio
import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from openai import OpenAI
from utils import create_task_response

PROMPT_STRUCTURE_INSTRUCTIONS = """
Output the response as JSON in this exact structure:
    {{
    "1": {{ "script": "Scene 1 script here", "imagePrompt": "Scene 1 image description", "effect": "pan_left", "duration": 15 }},
    "2": {{ "script": "Scene 2 script here", "imagePrompt": "Scene 2 image description", "effect": "zoom_in", "duration": 12 }},
    ...,
    "metadata": {{ "title": "Insert catchy video title based on the content", "description": "Insert a short YouTube-style description summarizing the story in 1–2 lines with hashtags if relevant" }}
    }}
Each scene should:
    • Be 10–15 seconds long
    • Push the story forward in a fun, engaging way
    • Use visual metaphors or animated whiteboard/doodle-style scenes
    • Include motion effects like zoom_in, pan_right, fade_in, wobble, etc.
"""


class NicheBase(ABC):
    """Base class for niche-specific handlers."""

    def __init__(self, openai_client: OpenAI):
        self.openai_client = openai_client
        self.content = None
        self.ai_response = None

    @abstractmethod
    async def fetch_content(self, request_id: str, **kwargs) -> AsyncGenerator[str, None]:
        """Retrieve content info for the niche and yield SSE messages."""
        yield

    @abstractmethod
    def build_prompt(self) -> str:
        """Return the prompt string used for script generation."""
        raise NotImplementedError

    def background_music_path(self) -> str | None:
        return None

    async def generate_script(self, request_id: str) -> AsyncGenerator[str, None]:
        """Generate a multi-scene script using OpenAI."""
        if self.content is None:
            yield create_task_response(request_id, "2", "Error", "No content data available.")
            return

        prompt = self.build_prompt()
        try:
            response = await asyncio.to_thread(
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
            )
            ai_output = response.choices[0].message.content
            try:
                json.loads(ai_output)
                self.ai_response = ai_output
                yield create_task_response(request_id, "2", "Success")
            except Exception as parse_error:
                yield create_task_response(request_id, "2", "Error", f"JSON parsing error: {str(parse_error)}")
        except Exception as e:
            yield create_task_response(request_id, "2", "Error", str(e))
