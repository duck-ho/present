from collections import Counter
from typing import List

import pandas as pd

from .analyzer import SENTIMENT_LABELS, SentimentResult
from .collectors.base import Article


def build_dataframe(articles: List[Article], sentiments: List[SentimentResult]) -> pd.DataFrame:
    rows = []
    for art, sent in zip(articles, sentiments):
        rows.append(
            {
                "published_at": art.published_at,
                "title": art.title,
                "source": art.source,
                "origin": art.origin,
                "url": art.url,
                "label": sent.label,
                "score": sent.score,
                "reason": sent.reason,
                "keywords": ", ".join(sent.keywords),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty and "published_at" in df.columns:
        df = df.sort_values("published_at", ascending=False, na_position="last").reset_index(drop=True)
    return df


def overall_score(sentiments: List[SentimentResult]) -> float:
    if not sentiments:
        return 0.0
    return sum(s.score for s in sentiments) / len(sentiments)


def label_distribution(sentiments: List[SentimentResult]) -> pd.DataFrame:
    counts = Counter(s.label for s in sentiments)
    data = [{"label": lbl, "count": counts.get(lbl, 0)} for lbl in SENTIMENT_LABELS]
    return pd.DataFrame(data)


def top_keywords(sentiments: List[SentimentResult], top_n: int = 15) -> pd.DataFrame:
    counter: Counter = Counter()
    for s in sentiments:
        for kw in s.keywords:
            if kw:
                counter[kw] += 1
    common = counter.most_common(top_n)
    return pd.DataFrame(common, columns=["keyword", "count"])


def daily_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "published_at" not in df.columns:
        return pd.DataFrame(columns=["date", "avg_score", "count"])
    work = df.dropna(subset=["published_at"]).copy()
    if work.empty:
        return pd.DataFrame(columns=["date", "avg_score", "count"])
    work["date"] = pd.to_datetime(work["published_at"]).dt.date
    grouped = work.groupby("date").agg(avg_score=("score", "mean"), count=("score", "size")).reset_index()
    return grouped.sort_values("date")
