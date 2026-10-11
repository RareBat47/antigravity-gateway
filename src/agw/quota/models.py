"""Data models for quota representation across models and accounts."""

import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ModelQuotaInfo(BaseModel):
    model_id: str
    model_family: str
    remaining_fraction: Optional[float] = None
    reset_time: Optional[str] = None
    source: str = "cloudcode"
    confidence: float = 1.0
    last_checked: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    @property
    def percentage(self) -> Optional[int]:
        if self.remaining_fraction is None:
            return None
        return int(round(self.remaining_fraction * 100))

    @property
    def is_exhausted(self) -> bool:
        if self.remaining_fraction is None:
            return False
        return self.remaining_fraction <= 0.01


class AccountQuotaSnapshot(BaseModel):
    account_id: str
    email_safe: str
    tier: str = "unknown"
    models: Dict[str, ModelQuotaInfo] = Field(default_factory=dict)
    gemini_average_fraction: Optional[float] = None
    claude_average_fraction: Optional[float] = None
    last_checked: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
