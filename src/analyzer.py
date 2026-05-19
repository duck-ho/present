import json
import os
from dataclasses import dataclass
from typing import List

from anthropic import Anthropic

from .collectors.base import Article


SENTIMENT_LABELS = ["매우 긍정", "긍정", "중립", "부정", "매우 부정"]
LABEL_TO_BUCKET = {
    "매우 긍정": "very_positive",
    "긍정": "positive",
    "중립": "neutral",
    "부정": "negative",
    "매우 부정": "very_negative",
}

MODEL_ID = "claude-opus-4-7"

SYSTEM_PROMPT = """당신은 금융 뉴스 감성 분석 전문가입니다.
주어진 기업/종목과 뉴스 기사 목록을 받아, 각 기사가 해당 기업/종목에 대해 갖는 투자 관점에서의 감성을 평가합니다.

평가 기준:
- 매우 긍정 (+0.6 ~ +1.0): 강한 호재, 실적 서프라이즈, 중대 계약, 신제품 흥행 등
- 긍정 (+0.2 ~ +0.6): 우호적 뉴스, 점진적 개선
- 중립 (-0.2 ~ +0.2): 사실 보도, 영향 불명확
- 부정 (-0.6 ~ -0.2): 우려 사항, 가이던스 하향, 경쟁 심화
- 매우 부정 (-1.0 ~ -0.6): 심각한 악재, 회계 이슈, 대규모 소송, 리콜

반드시 유효한 JSON 배열 한 개만 반환하세요. 다른 텍스트, 마크다운 코드 블록을 포함하지 마세요.
형식:
[
  {"index": 0, "label": "긍정", "score": 0.45, "reason": "한국어 한 문장 근거", "keywords": ["키워드1", "키워드2"]},
  ...
]
- label은 정확히 다음 중 하나: 매우 긍정, 긍정, 중립, 부정, 매우 부정
- score는 -1.0 ~ +1.0 사이 소수
- reason은 30자~80자 한국어 한 문장
- keywords는 기사에서 핵심 단어 1~3개
- 모든 입력 기사에 대해 동일한 index로 응답
"""


@dataclass
class SentimentResult:
    label: str
    score: float
    reason: str
    keywords: List[str]

    @property
    def bucket(self) -> str:
        return LABEL_TO_BUCKET.get(self.label, "neutral")


def _build_user_prompt(target: str, articles: List[Article]) -> str:
    lines = [f"분석 대상: {target}", "", "기사 목록:"]
    for i, art in enumerate(articles):
        body = art.text_for_analysis.replace("\n", " ")
        if len(body) > 600:
            body = body[:600] + "..."
        lines.append(f"[{i}] ({art.origin or art.source}) {body}")
    lines.append("")
    lines.append("위 모든 기사에 대해 JSON 배열로 응답하세요.")
    return "\n".join(lines)


def _extract_json(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in model response")
    return json.loads(text[start : end + 1])


def analyze_articles(
    target: str,
    articles: List[Article],
    batch_size: int = 10,
) -> List[SentimentResult]:
    if not articles:
        return []

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."
        )

    client = Anthropic(api_key=api_key)
    results: List[SentimentResult] = []

    for start in range(0, len(articles), batch_size):
        batch = articles[start : start + batch_size]
        user_prompt = _build_user_prompt(target, batch)

        message = client.messages.create(
            model=MODEL_ID,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )
        parsed = _extract_json(raw_text)

        by_index = {int(item.get("index", -1)): item for item in parsed}
        for i, _ in enumerate(batch):
            item = by_index.get(i)
            if item is None:
                results.append(
                    SentimentResult(label="중립", score=0.0, reason="분석 실패", keywords=[])
                )
                continue
            label = item.get("label", "중립")
            if label not in LABEL_TO_BUCKET:
                label = "중립"
            try:
                score = float(item.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            score = max(-1.0, min(1.0, score))
            results.append(
                SentimentResult(
                    label=label,
                    score=score,
                    reason=str(item.get("reason", "")).strip(),
                    keywords=[str(k).strip() for k in item.get("keywords", []) if str(k).strip()],
                )
            )

    return results


def summarize_themes(target: str, articles: List[Article], sentiments: List[SentimentResult]) -> str:
    """Ask Claude for a brief Korean-language thematic summary of the news set."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return ""
    if not articles:
        return ""

    client = Anthropic(api_key=api_key)
    lines = [f"분석 대상: {target}", "", "기사 + 감성 결과:"]
    for art, sent in zip(articles, sentiments):
        body = art.text_for_analysis.replace("\n", " ")
        if len(body) > 250:
            body = body[:250] + "..."
        lines.append(f"- [{sent.label} {sent.score:+.2f}] {body}")
    user_prompt = (
        "\n".join(lines)
        + "\n\n위 뉴스 묶음의 핵심 이슈/테마를 한국어 3~5개 불릿으로 요약하세요. "
        "각 불릿은 한 줄, 끝에 (긍정/중립/부정 경향)을 표기하세요. "
        "마크다운 코드 블록 없이 텍스트만 반환하세요."
    )

    message = client.messages.create(
        model=MODEL_ID,
        max_tokens=600,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    ).strip()
