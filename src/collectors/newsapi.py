import os
from datetime import datetime
from typing import List

import requests

from .base import Article


def collect_newsapi(query: str, limit: int = 10, language: str = "en") -> List[Article]:
    """NewsAPI.org collector. Returns [] if no API key is configured."""
    api_key = os.getenv("NEWSAPI_KEY", "").strip()
    if not api_key:
        return []

    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": limit,
        "apiKey": api_key,
    }
    try:
        resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if data.get("status") != "ok":
        return []

    articles: List[Article] = []
    for item in data.get("articles", [])[:limit]:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url or title == "[Removed]":
            continue
        published_at = None
        published_raw = item.get("publishedAt")
        if published_raw:
            try:
                published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        source = ((item.get("source") or {}).get("name") or "NewsAPI").strip()
        articles.append(
            Article(
                title=title,
                url=url,
                source=source,
                published_at=published_at,
                summary=(item.get("description") or "").strip(),
                origin=f"NewsAPI ({language})",
            )
        )
    return articles
