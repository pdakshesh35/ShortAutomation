from openai import OpenAI
from .news import NewsNiche


def get_handler(niche: str, openai_client: OpenAI):
    """Factory to return a niche handler based on string name."""
    niche = niche.lower()
    if niche == "news":
        return NewsNiche(openai_client)
    raise ValueError(f"Unsupported niche: {niche}")
