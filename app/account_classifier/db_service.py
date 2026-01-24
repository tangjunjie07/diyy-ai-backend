"""DB persistence services for account_classifier.

This dify-ai-backend variant persists into the ai-business-automation schema
defined in apps/web/prisma/schema.prisma:

- claude_predictions (model ClaudePrediction)
- mf_journal_entries (model MfJournalEntry)

This module depends on asyncpg (Pool/Connection).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.account_classifier.formatting import build_journal_memo

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    # Keep naive UTC datetimes for compatibility with existing DB schemas.
    return datetime.utcnow()


async def _set_rls_tenant(conn: Any, tenant_id: str) -> None:
    """Best-effort: set per-session tenant id for Postgres RLS."""

    try:
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
    except Exception as e:
        logger.debug("Failed to set RLS tenant_id=%s: %s", tenant_id, e)


def _parse_date(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    # Accept YYYY-MM-DD or YYYY/MM/DD
    normalized = raw.replace("/", "-")
    try:
        return datetime.strptime(normalized, "%Y-%m-%d")
    except Exception:
        return None


@dataclass
class ClaudePredictionService:
    db_pool: Any

    async def save_prediction(
        self,
        *,
        tenant_id: str,
        invoice_id: Optional[str],
        input_vendor: str,
        input_description: str,
        input_amount: float,
        input_direction: str,
        predicted_account: str,
        account_confidence: float,
        reasoning: Optional[str],
        matched_vendor_id: Optional[str],
        matched_vendor_code: Optional[str],
        matched_vendor_name: Optional[str],
        vendor_confidence: Optional[float],
        matched_account_id: Optional[str],
        matched_account_code: Optional[str],
        matched_account_name: Optional[str],
        claude_model: str,
        tokens_used: Optional[int],
        raw_response: Optional[str],
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> str:
        prediction_id = str(uuid.uuid4())
        now = _utcnow()

        query = """
        INSERT INTO claude_predictions (
            id,
            tenant_id,
            input_vendor,
            input_description,
            input_amount,
            input_direction,
            predicted_account,
            account_confidence,
            reasoning,
            matched_vendor_id,
            matched_vendor_code,
            matched_vendor_name,
            vendor_confidence,
            matched_account_id,
            matched_account_code,
            matched_account_name,
            claude_model,
            tokens_used,
            raw_response,
            status,
            error_message,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9,
            $10, $11, $12, $13,
            $14, $15, $16,
            $17, $18, $19,
            $20, $21,
            $22,
            $23
        )
        RETURNING id
        """

        async with self.db_pool.acquire() as conn:
            await _set_rls_tenant(conn, tenant_id)

            row = await conn.fetchrow(
                query,
                prediction_id,
                tenant_id,
                input_vendor,
                input_description,
                float(input_amount or 0),
                input_direction,
                predicted_account,
                float(account_confidence or 0),
                reasoning,
                matched_vendor_id,
                matched_vendor_code,
                matched_vendor_name,
                vendor_confidence,
                matched_account_id,
                matched_account_code,
                matched_account_name,
                claude_model or "unknown",
                int(tokens_used) if tokens_used is not None else None,
                raw_response,
                status,
                error_message,
                now,
                now,
            )

        return str(row["id"]) if row and "id" in row else ""


@dataclass
class MfJournalEntryService:
    db_pool: Any

    async def save_journal_entry(
        self,
        *,
        tenant_id: str,
        claude_prediction_id: Optional[str],
        transaction_date: Optional[datetime],
        transaction_type: str,
        income_amount: Optional[float],
        expense_amount: Optional[float],
        account_subject: str,
        matched_account_id: Optional[str],
        matched_account_code: Optional[str],
        vendor: Optional[str],
        matched_vendor_id: Optional[str],
        matched_vendor_code: Optional[str],
        description: Optional[str],
        account_book: Optional[str],
        tax_category: Optional[str],
        memo: Optional[str],
        tag_names: Optional[str],
        status: str = "draft",
        error_message: Optional[str] = None,
    ) -> str:
        entry_id = str(uuid.uuid4())
        now = _utcnow()

        query = """
        INSERT INTO mf_journal_entries (
            id,
            tenant_id,
            claude_prediction_id,
            transaction_date,
            transaction_type,
            income_amount,
            expense_amount,
            account_subject,
            matched_account_id,
            matched_account_code,
            vendor,
            matched_vendor_id,
            matched_vendor_code,
            description,
            account_book,
            tax_category,
            memo,
            tag_names,
            csv_exported,
            mf_imported,
            status,
            error_message,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            $8, $9, $10,
            $11, $12, $13,
            $14, $15, $16,
            $17, $18,
            $19,
            $20,
            $21,
            $22,
            $23,
            $24
        )
        RETURNING id
        """

        async with self.db_pool.acquire() as conn:
            await _set_rls_tenant(conn, tenant_id)

            row = await conn.fetchrow(
                query,
                entry_id,
                tenant_id,
                claude_prediction_id,
                transaction_date,
                transaction_type,
                income_amount,
                expense_amount,
                account_subject,
                matched_account_id,
                matched_account_code,
                vendor,
                matched_vendor_id,
                matched_vendor_code,
                description,
                account_book,
                tax_category,
                memo,
                tag_names,
                False,
                False,
                status,
                error_message,
                now,
                now,
            )

        return str(row["id"]) if row and "id" in row else ""


def convert_transaction_to_mf_journal_fields(tx: Dict[str, Any]) -> Dict[str, Any]:
    direction = (tx.get("direction") or "expense").lower()
    amount = float(tx.get("amount") or 0)
    abs_amount = abs(amount)

    account_subject = tx.get("accountName") or ("雑費" if direction == "expense" else "売上高")
    transaction_date = _parse_date(tx.get("date"))
    if transaction_date is None:
        transaction_date = _utcnow()

    income_amount = abs_amount if direction == "income" else None
    expense_amount = abs_amount if direction != "income" else None

    default_tax = "課税売上10%" if direction == "income" else "課税仕入10%"

    memo_text = build_journal_memo(
        reason=tx.get("reasoning") or tx.get("claude_description") or tx.get("memo"),
        account_confidence=tx.get("account_confidence") if tx.get("account_confidence") is not None else tx.get("confidence"),
        vendor_confidence=tx.get("vendor_confidence"),
    )

    return {
        "transaction_date": transaction_date,
        "transaction_type": direction,
        "income_amount": income_amount,
        "expense_amount": expense_amount,
        "account_subject": account_subject,
        "matched_account_id": tx.get("matched_account_id"),
        "matched_account_code": tx.get("matched_account_code"),
        "vendor": tx.get("vendor"),
        "matched_vendor_id": tx.get("matched_vendor_id"),
        "matched_vendor_code": tx.get("matched_vendor_code"),
        # Keep mf_journal_entries.description aligned with claude_predictions.reasoning.
        "description": tx.get("reasoning") or tx.get("claude_description") or tx.get("description"),
        "account_book": tx.get("account_book") or "普通預金",
        "tax_category": tx.get("tax_category") or default_tax,
        "memo": memo_text,
        "tag_names": tx.get("tag_names") or "AI自動仕訳",
    }
