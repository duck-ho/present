from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: Optional[datetime]
    summary: str = ""
    origin: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d

    @property
    def text_for_analysis(self) -> str:
        parts = [self.title]
        if self.summary and self.summary.strip() != self.title.strip():
            parts.append(self.summary)
        return "\n".join(parts).strip()
