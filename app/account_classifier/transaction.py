from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Transaction(BaseModel):
    """Internal normalized transaction model for account_classifier.

    The rest of the codebase still uses dicts, but this model provides a single
    normalization point to reduce "stringly-typed" drift.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    date: Optional[Union[str, datetime]] = None
    vendor: str = ""
    description: str = ""
    amount: float = 0.0
    direction: Literal["expense", "income"] = "expense"

    accountName: Optional[str] = None
    subAccountItem: Optional[str] = None
    fileName: Optional[str] = None

    reasoning: Optional[str] = None
    claude_description: Optional[str] = None

    confidence: Optional[float] = None
    account_confidence: Optional[float] = None
    vendor_confidence: Optional[float] = None

    ref_: Any = Field(default=None, alias="_ref")

    @field_validator("vendor", "description", mode="before")
    @classmethod
    def _coerce_str(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    @field_validator("direction", mode="before")
    @classmethod
    def _normalize_direction(cls, value: Any) -> str:
        raw = ("" if value is None else str(value)).strip().lower()
        if raw in {"income", "in", "収入", "入金"}:
            return "income"
        if raw in {"expense", "out", "支出", "出金"}:
            return "expense"
        # Heuristic fallbacks
        if "in" in raw or "収" in raw:
            return "income"
        return "expense"


def normalize_transaction_dict(tx: Any) -> Optional[dict]:
    if not isinstance(tx, dict):
        return None
    try:
        model = Transaction.model_validate(tx)
        # Keep extra fields and keep the original `_ref` alias.
        return model.model_dump(by_alias=True)
    except Exception:
        return None


def normalize_transactions(items: Iterable[Any]) -> List[dict]:
    out: List[dict] = []
    for it in items:
        normalized = normalize_transaction_dict(it)
        if normalized is not None:
            out.append(normalized)
    return out
