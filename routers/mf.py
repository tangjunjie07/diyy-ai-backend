from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import secrets
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.aliases import AliasChoices

from app.account_classifier.pipeline import run_account_classifier
from app.account_classifier.flexible_ocr_loader import extract_transactions_from_pending_journal_data
from app.account_classifier.predictor_claude import ClaudePredictor
from app.repos.tenant_api_secrets_repo import PROVIDER_ANTHROPIC, get_tenant_api_secret
from auth import verify_token
from config import APP_PUBLIC_URL
from services.chat_session_service import chat_session_service

logger = logging.getLogger(__name__)

try:
    import asyncpg  # type: ignore
except Exception:  # pragma: no cover
    asyncpg = None

router = APIRouter(prefix="/mf", tags=["MF"])

_db_pool: Any = None
_db_pool_lock = asyncio.Lock()

# In-memory CSV export store (best-effort; TTL-based). This enables browser downloads via a GET link.
_csv_exports: Dict[str, Dict[str, Any]] = {}
_csv_exports_lock = asyncio.Lock()
_CSV_EXPORT_TTL_SECONDS = int(os.getenv("MF_CSV_EXPORT_TTL_SECONDS", "900"))  # default 15 minutes


def _csv_utf8_with_bom(csv_text: str) -> bytes:
    # Excel on Windows often mis-detects UTF-8 without BOM.
    return ("\ufeff" + (csv_text or "")).encode("utf-8")


async def _store_csv_export(
    csv_text: str,
    *,
    tenant_id: Optional[str] = None,
    mf_journal_entry_ids: Optional[List[str]] = None,
) -> Dict[str, str]:
    export_id = str(uuid.uuid4())
    download_token = secrets.token_urlsafe(32)
    now = time.time()
    async with _csv_exports_lock:
        # Cleanup expired exports opportunistically.
        cutoff = now - _CSV_EXPORT_TTL_SECONDS
        expired_keys = [k for k, v in _csv_exports.items() if float(v.get("created_at", 0)) < cutoff]
        for k in expired_keys:
            _csv_exports.pop(k, None)

        _csv_exports[export_id] = {
            "created_at": now,
            "csv": csv_text,
            "token": download_token,
            "tenant_id": tenant_id,
            "mf_journal_entry_ids": list(mf_journal_entry_ids or []),
        }
    return {"export_id": export_id, "token": download_token}


async def _get_csv_export_record(export_id: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    async with _csv_exports_lock:
        record = _csv_exports.get(export_id)
        if not record:
            return None
        created_at = float(record.get("created_at", 0))
        if created_at < (now - _CSV_EXPORT_TTL_SECONDS):
            _csv_exports.pop(export_id, None)
            return None
        return dict(record)


async def _get_csv_export(export_id: str) -> Optional[str]:
    now = time.time()
    async with _csv_exports_lock:
        record = _csv_exports.get(export_id)
        if not record:
            return None
        created_at = float(record.get("created_at", 0))
        if created_at < (now - _CSV_EXPORT_TTL_SECONDS):
            _csv_exports.pop(export_id, None)
            return None
        return str(record.get("csv") or "")


async def _get_csv_export_token(export_id: str) -> Optional[str]:
    now = time.time()
    async with _csv_exports_lock:
        record = _csv_exports.get(export_id)
        if not record:
            return None
        created_at = float(record.get("created_at", 0))
        if created_at < (now - _CSV_EXPORT_TTL_SECONDS):
            _csv_exports.pop(export_id, None)
            return None
        token = record.get("token")
        return str(token) if token else None


async def _mark_mf_journal_entries_exported(*, tenant_id: str, entry_ids: List[str]) -> None:
    if not tenant_id or not entry_ids:
        return

    try:
        pool = await _get_db_pool()
    except HTTPException as e:
        if e.status_code == 503:
            logger.info("Skipping export flag update: DB unavailable (%s)", e.detail)
            return
        raise

    async with pool.acquire() as conn:
        try:
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
        except Exception:
            pass

        await conn.execute(
            """
            UPDATE mf_journal_entries
            SET
                csv_exported = TRUE,
                csv_exported_at = COALESCE(csv_exported_at, NOW()),
                status = CASE WHEN status IN ('draft', 'ready') THEN 'exported' ELSE status END,
                updated_at = NOW()
            WHERE tenant_id = $1
              AND id = ANY($2::text[])
            """,
            str(tenant_id),
            entry_ids,
        )


async def _get_db_pool() -> Any:
    """Create a singleton asyncpg pool for pipeline DB persistence."""
    global _db_pool
    if _db_pool is not None:
        return _db_pool

    async with _db_pool_lock:
        if _db_pool is not None:
            return _db_pool

        if asyncpg is None:
            raise HTTPException(
                status_code=503,
                detail="DB persistence is unavailable: asyncpg is not installed",
            )

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise HTTPException(
                status_code=503,
                detail=(
                    "DATABASE_URL is not set. Set DATABASE_URL (PostgreSQL DSN) before calling /mf/register. "
                    "Example: postgresql://USER:PASSWORD@HOST:5432/DBNAME"
                ),
            )

        try:
            _db_pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Failed to connect to DATABASE_URL. "
                    "Check host/port/credentials and that the DB is reachable from where this API is running. "
                    f"Error: {type(e).__name__}: {e}"
                ),
            )
        return _db_pool


class JournalCsvRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    tenant_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("tenantId", "tenant_id"),
    )
    # Note: persistDb / generateMfCsv flags are intentionally not modeled.
    # This endpoint always persists to DB and always generates MF CSV.

    # Either provide normalized transactions, or inferred_accounts (+ optional ocr_data/file_name).
    transactions: Optional[List[Dict[str, Any]]] = None
    inferred_accounts: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        validation_alias=AliasChoices("inferredAccounts", "inferred_accounts"),
    )
    ocr_data: Optional[Dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("ocrData", "ocr_data"),
    )
    file_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("fileName", "file_name"),
    )

    # Dify OCR output shape (stringified JSON array)
    pending_journal_data: Optional[Any] = Field(
        default=None,
        validation_alias=AliasChoices("pending_journal_data", "pendingJournalData"),
    )


@router.post("/register")
async def register_pipeline(
    payload: JournalCsvRequest,
    as_json: bool = Query(True),
    token_payload: dict = Depends(verify_token),
    request: Request = None,
):
    """Dify-callable endpoint: generate MF journal CSV via account_classifier pipeline.

    - Returns JSON by default (better for Dify HTTP node).
    - Set `as_json=false` to return raw CSV as text/csv.
    """
    tenant_id = payload.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenantId is required (in JSON body)")

    # Prefer DB persistence when available, but don't hard-fail local/dev flows.
    persist_db = True
    db_pool: Any = None
    try:
        db_pool = await _get_db_pool()
    except HTTPException as e:
        if e.status_code == 503:
            persist_db = False
        else:
            raise

    # Prefer tenant-scoped Anthropic key when available.
    predictor: Optional[ClaudePredictor] = None
    try:
        api_key = await get_tenant_api_secret(None, tenant_id=tenant_id, provider=PROVIDER_ANTHROPIC)
        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if api_key:
            predictor = ClaudePredictor(api_key=api_key)
    except Exception as e:
        # If Claude can't be initialized, keep going (CSV can still be generated with fallbacks).
        # Errors will be visible in DB persistence payload (claude_model will default).
        predictor = None

    transactions = payload.transactions
    if transactions is None and payload.pending_journal_data is not None:
        transactions = extract_transactions_from_pending_journal_data(
            pending_journal_data=payload.pending_journal_data
        )

    if not transactions:
        raise HTTPException(
            status_code=400,
            detail=(
                "No transactions extracted. Provide `transactions` or a valid `pending_journal_data` JSON array. "
                "Tip: in Dify, send pending_journal_data as a real JSON array (not a string with embedded quotes)."
            ),
        )

    result = await run_account_classifier(
        inferred_accounts=payload.inferred_accounts,
        ocr_data=payload.ocr_data,
        file_name=payload.file_name,
        transactions=transactions,
        predictor=predictor,
        generate_mf_csv=True,
        persist_db=persist_db,
        db_pool=db_pool,
        tenant_id=tenant_id,
        invoice_id=None,
    )

    csv_text = result.mf_csv or ""
    if not csv_text:
        raise HTTPException(status_code=400, detail="MF CSV generation failed (no output)")

    if as_json:
        export_info = await _store_csv_export(
            csv_text,
            tenant_id=str(tenant_id),
            mf_journal_entry_ids=list(getattr(result, "persisted_entry_ids", []) or []),
        )
        export_id = export_info["export_id"]
        token = export_info["token"]
        base_url = APP_PUBLIC_URL
        download_url = f"{base_url}/mf/exports/{export_id}.csv?token={token}" if base_url else None
        return {
            "count": len(result.transactions),
            "persisted_count": int(result.persisted_count or 0),
            "db_persistence": "enabled" if persist_db else "skipped",
            "csv_text": csv_text,
            "csv_export_id": export_id,
            "csv_download_url": download_url,
            "transactions": result.transactions,
            "errors": result.errors,
        }

    return Response(content=_csv_utf8_with_bom(csv_text), media_type="text/csv; charset=utf-8")


@router.get("/exports/{export_id}.csv")
async def download_csv_export(export_id: str, token: str = Query(...)):
    """Download a recently generated MF CSV.

    This endpoint is intended for browser downloads from a Dify chat UI.
    It uses a short-lived signed token instead of normal API auth.
    """
    record = await _get_csv_export_record(export_id)
    if not record:
        raise HTTPException(status_code=404, detail="CSV export not found (expired or invalid id)")
    expected = str(record.get("token") or "")
    if not expected:
        raise HTTPException(status_code=404, detail="CSV export not found (expired or invalid id)")
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid or expired download token")

    csv_text = str(record.get("csv") or "")
    if not csv_text:
        raise HTTPException(status_code=404, detail="CSV export not found (expired or invalid id)")

    tenant_id = record.get("tenant_id")
    entry_ids = record.get("mf_journal_entry_ids")
    if isinstance(tenant_id, str) and tenant_id.strip() and isinstance(entry_ids, list) and entry_ids:
        try:
            await _mark_mf_journal_entries_exported(tenant_id=tenant_id, entry_ids=[str(x) for x in entry_ids if x])
        except Exception:
            logger.exception("Failed to update mf_journal_entries export flags for export_id=%s", export_id)

    headers = {
        "Content-Disposition": f'attachment; filename="mf_journal_{export_id}.csv"',
    }
    return Response(
        content=_csv_utf8_with_bom(csv_text),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


# Backward-compatible alias (older flows may still call this path)
@router.post("/journal/csv")
async def generate_journal_csv(
    payload: JournalCsvRequest,
    as_json: bool = Query(True),
    token_payload: dict = Depends(verify_token),
):
    return await register_pipeline(payload=payload, as_json=as_json, token_payload=token_payload)

def call_money_forward_api(item: dict):
    if item.get("totalAmount", 0) <= 0:
        raise Exception("金額不正：金額必須大於 0")
    return True

@router.post("/register/mf-api")
async def register_to_mf(request: Request, token_payload: dict = Depends(verify_token)):
    if chat_session_service is None:
        raise HTTPException(
            status_code=500,
            detail="Prisma client is not generated. Run `python -m prisma generate --schema prisma/schema.prisma` (in the backend venv) before using /mf/register/mf-api.",
        )
    body = await request.json()
    tenant_id = body.get("tenantId")
    if not tenant_id:
        return {"success": False, "error": "tenantId is required"}
    json_text = body.get("journal_data", "[]")
    try:
        journal_list = json.loads(json_text) if isinstance(json_text, str) else json_text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析失敗: {e}")
    success_count = 0
    failure_count = 0
    details = []
    failed_items_data = []
    for item in journal_list:
        filename = item.get("filename", "unknown")
        # OCR返却項目名に合わせてchat_file_idを取得
        chat_file_id = item.get("chat_file_id") or item.get("chatFileId")
        # 金額・日付は取れた場合のみ更新
        extracted_amount = item.get("totalAmount") if "totalAmount" in item else None
        extracted_date = item.get("invoiceDate") if "invoiceDate" in item else None
        try:
            call_money_forward_api(item)
            # MF連携成功時にChatFileを更新
            if chat_file_id and tenant_id:
                update_kwargs = {"chat_file_id": chat_file_id, "tenant_id": tenant_id, "status": "mf_completed"}
                if extracted_amount is not None:
                    update_kwargs["extracted_amount"] = extracted_amount
                if extracted_date is not None:
                    update_kwargs["extracted_date"] = extracted_date
                await chat_session_service.update_chat_file(**update_kwargs)
            success_count += 1
            details.append({
                "filename": filename,
                "status": "success"
            })
        except Exception as e:
            failure_count += 1
            details.append({
                "filename": filename,
                "status": "failed",
                "error": str(e)
            })
            failed_items_data.append(item)
        time.sleep(0.1)
    return {
        "total": len(journal_list),
        "success_count": success_count,
        "failure_count": failure_count,
        "details": details,
        "failed_items": json.dumps(failed_items_data, ensure_ascii=False) if failed_items_data else ""
    }
