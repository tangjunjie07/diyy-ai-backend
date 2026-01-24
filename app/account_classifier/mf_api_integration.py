"""Money Forward (MF) API integration helper.

Copied from services/ingestion-service/app/account_classifier/mf_api_integration.py

Note: This module is not required for basic classification/CSV export.
It depends on httpx.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class MoneyForwardClient:
    base_url: str
    access_token: str

    @classmethod
    def from_env(cls) -> "MoneyForwardClient":
        base_url = os.getenv("MF_API_BASE_URL", "https://api.biz.moneyforward.com")
        access_token = os.getenv("MF_ACCESS_TOKEN", "")
        if not access_token:
            raise ValueError("MF_ACCESS_TOKEN is required")
        return cls(base_url=base_url, access_token=access_token)

    async def post_journal(self, *, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx is required. Install with: pip install httpx") from e

        url = f"{self.base_url.rstrip('/')}/api/v1/journals"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()


def build_mf_journal_payload_from_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal payload builder.

    This is intentionally a stub-like helper; MF API schema may vary.
    """
    direction = tx.get("direction") or "expense"
    amount = float(tx.get("amount") or 0)
    account = tx.get("accountName") or ("雑費" if direction == "expense" else "売上高")

    if direction == "expense":
        debit = account
        credit = "普通預金"
    else:
        debit = "普通預金"
        credit = account

    return {
        "transaction_date": tx.get("date"),
        "description": tx.get("description"),
        "lines": [
            {"side": "debit", "account": debit, "amount": abs(amount)},
            {"side": "credit", "account": credit, "amount": abs(amount)},
        ],
        "vendor": tx.get("vendor"),
    }
