from datetime import datetime
from typing import List
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

from .base import Article

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _parse_date(entry) -> datetime | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except (TypeError, ValueError):
            return None
    return None


def _clean_summary(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    return soup.get_text(" ", strip=True)


def _build_url(query: str, language: str) -> str:
    q = quote(query)
    if language == "ko":
        return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def collect_google_news(query: str, limit: int = 10, language: str = "ko") -> List[Article]:
    url = _build_url(query, language)
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except requests.RequestException:
        return []
    articles: List[Article] = []
    for entry in feed.entries[:limit]:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue
        source = ""
        if hasattr(entry, "source") and getattr(entry.source, "title", None):
            source = entry.source.title
        articles.append(
            Article(
                title=title,
                url=link,
                source=source or "Google News",
                published_at=_parse_date(entry),
                summary=_clean_summary(getattr(entry, "summary", "")),
                origin=f"Google News ({language})",
            )
        )
    return articles
