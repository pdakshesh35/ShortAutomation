import asyncio
import os
import json
import uuid
from newsapi import NewsApiClient
from runware import Runware, IImageInference
from utils import create_task_response
from .base import NicheBase, PROMPT_STRUCTURE_INSTRUCTIONS


class NewsNiche(NicheBase):
    """Niche handler for news videos."""

    async def fetch_content(self, request_id: str, country: str, category: str, query: str) -> asyncio.AsyncGenerator[str, None]:
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key:
            yield create_task_response(request_id, "1", "Error", "NEWS_API_KEY not set in environment.")
            return
        newsapi = NewsApiClient(api_key=api_key)
        kwargs = {"country": country, "category": category, "page_size": 5}
        if query:
            kwargs["q"] = query
        try:
            news_json = await asyncio.to_thread(newsapi.get_top_headlines, **kwargs)
        except Exception as e:
            news_json = {"error": str(e)}
        valid_article = None
        if "articles" in news_json and isinstance(news_json["articles"], list):
            for article in news_json["articles"]:
                if article.get("title") and article.get("description") and article.get("content"):
                    valid_article = article
                    break
        if valid_article:
            self.content = valid_article
            msg = (
                f"Fetched news: Title: {valid_article['title']}, Description: {valid_article['description']}, Content: {valid_article['content']}"
            )
            yield create_task_response(request_id, "1", "Success", msg)
        else:
            yield create_task_response(request_id, "1", "Error", "No valid news article found with all required fields.")

    def build_prompt(self) -> str:
        if not self.content:
            return ""
        news_content = self.content.get("content", "")
        prompt = f"""
            Act as a viral content strategist and news scriptwriter for vertical video platforms like YouTube Shorts, Instagram Reels, TikTok, and Snapchat.
            Your task is to break down the following news story into a short-form, highly engaging 2-minute narration targeted at college students and young professionals (ages 18–30).
            Tone: Witty, informative, and lightly meme-style — like a confident, sarcastic best friend who knows her facts and isn’t afraid to drop a punchline.
            Voice: Female with strong personality. Include rhetorical hooks, Gen Z-friendly humor, and clever metaphors. Feel free to reference pop culture, TikTok trends, or modern slang in a tasteful way.
            News Style: Cover all types — breaking news, trending topics, weird facts, tech, social issues, etc.
            {PROMPT_STRUCTURE_INSTRUCTIONS}

            End the final scene with a strong call to action, like:
            “If you liked this, hit follow — you deserve better news.”
            Begin with this news story:
            {news_content}
        """
        return prompt

    def background_music_path(self) -> str | None:
        return os.path.join("data", "news-bg-music.mp3")
