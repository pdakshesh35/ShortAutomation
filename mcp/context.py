import os
import uuid
from openai import OpenAI
from niches import get_handler


class MCPContext:
    """State for an MCP session."""

    def __init__(self, niche: str):
        self.request_id = str(uuid.uuid4())
        # Each context maintains its own OpenAI client
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.handler = get_handler(niche, self.openai_client)
        self.ai_response: str | None = None

    def background_music_path(self) -> str | None:
        return self.handler.background_music_path()
