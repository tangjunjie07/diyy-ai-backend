from __future__ import annotations

"""account_classifier のパイプライン（単一入口）

このモジュールは、取引データに対して以下の一連処理を（必要に応じて）まとめて実行します。

処理フロー（概略）:
1) 入力の正規化
   - `inferred_accounts`（OCR/推論結果）から `transactions` 形式へ変換
   - もしくは `transactions`（正規化済み）をそのまま受け取る
2) Claude による分類（best-effort）
    - 利用可能なら Claude で「勘定科目マスタ照合」+「取引先マスタ照合」を実行
    - account_masters.json / vendor_masters.json をロードして Claude に渡す（ただしトークン節約のため候補は predictor 側で絞り込み）
   - 利用不可なら分類をスキップ（例外で落とさない）
3) MF 仕訳帳 CSV の生成（任意）
   - 分類済み `transactions` から CSV テキストを生成
4) DB への保存（任意）
   - `claude_predictions` と `mf_journal_entries` へ書き込み
   - RLS/テナント分離の前提として `tenant_id` を要求

主なエントリポイント:
- `run_account_classifier`（async）: 正規化→分類→CSV→DB を統合した単一入口
- `run_pipeline`（sync）: 既存の batch-process 互換（JSONL→CSV）
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.account_classifier.flexible_ocr_loader import extract_transactions_from_inferred_accounts
from app.account_classifier.mf_export_service import MfExportService
from app.account_classifier.predictor_claude import ClaudePredictor
from app.account_classifier.transaction import normalize_transactions

logger = logging.getLogger(__name__)


@dataclass
class AccountClassifierPipelineResult:
    """account_classifier.pipeline の各エントリポイントで共通に返す結果オブジェクト。"""

    transactions: List[Dict[str, Any]]
    mf_csv: Optional[str]
    persisted_count: int = 0
    persisted_entry_ids: List[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.persisted_entry_ids is None:
            self.persisted_entry_ids = []
        if self.errors is None:
            self.errors = []


def classify_transactions_with_claude(
    txs: List[Dict[str, Any]],
    predictor: Optional[ClaudePredictor] = None,
) -> List[Dict[str, Any]]:
    """Claude predictor を使って各取引の勘定科目分類と取引先マスタ照合を行います（best-effort）。

    - `tx` の dict を in-place で更新します。
    - `tx['_ref']` がある場合、元の inferred_accounts 側にも結果を書き戻します。
    """

    # IMPORTANT:
    # In dify-ai-backend we only call Claude when a predictor is explicitly provided
    # (i.e., when an API key was found by the caller). Do not auto-initialize here.
    if predictor is None:
        return txs

    vendor_masters: Optional[List[Dict[str, Any]]] = None
    account_masters: Optional[List[Dict[str, Any]]] = None
    try:
        from app.account_classifier.master_loader import get_master_loader

        loader = get_master_loader()
        vendor_masters = loader.load_vendor_masters(active_only=True)
        account_masters = loader.load_account_masters()
    except Exception as e:
        logger.debug("Failed to load masters for Claude matching: %s", e)
        vendor_masters = None
        account_masters = None

    for tx in txs:
        try:
            pred = predictor.predict(
                vendor=str(tx.get("vendor") or ""),
                description=str(tx.get("description") or ""),
                amount=float(tx.get("amount") or 0),
                direction=str(tx.get("direction") or "expense"),
                vendor_masters=vendor_masters,
                account_masters=account_masters,
            )

            tx["accountName"] = pred.account
            tx["confidence"] = pred.confidence
            # Unify the "reasoning" (claude_predictions) and "description" (mf_journal_entries)
            # data source so both columns represent the same underlying Claude-provided text.
            shared_text = None
            # Prefer Claude JSON `reasoning` as the shared source of truth.
            if getattr(pred, "reasoning", None):
                shared_text = pred.reasoning
            elif getattr(pred, "description", None):
                shared_text = pred.description

            if shared_text is not None:
                tx["reasoning"] = shared_text
                tx["claude_description"] = shared_text

            if getattr(pred, "matched_account_code", None):
                tx["matched_account_code"] = pred.matched_account_code
            if getattr(pred, "matched_account_name", None):
                tx["matched_account_name"] = pred.matched_account_name
            if getattr(pred, "account_confidence", None) is not None:
                tx["account_confidence"] = pred.account_confidence

            if pred.matched_vendor_id:
                tx["matched_vendor_id"] = pred.matched_vendor_id
                tx["matched_vendor_name"] = pred.matched_vendor_name
                tx["vendor_confidence"] = pred.vendor_confidence

            if pred.raw_response is not None:
                tx["claude_raw_response"] = pred.raw_response
            if pred.model is not None:
                tx["claude_model"] = pred.model
            if pred.tokens_used is not None:
                tx["claude_tokens_used"] = pred.tokens_used

            ref = tx.get("_ref")
            if isinstance(ref, dict):
                ref["accountItem"] = pred.account
                ref["confidence"] = pred.confidence
                ref["reasoning"] = pred.reasoning
                if getattr(pred, "description", None):
                    ref["claudeDescription"] = pred.description
                if pred.matched_vendor_id:
                    ref["matchedVendorId"] = pred.matched_vendor_id
                    ref["matchedVendorName"] = pred.matched_vendor_name
                    ref["vendorConfidence"] = pred.vendor_confidence
        except Exception as e:
            logger.debug("Claude classification failed for tx=%s: %s", tx, e)

    return txs


def build_mf_csv_from_inferred_accounts(
    inferred_accounts: Optional[List[Dict[str, Any]]],
    ocr_data: Optional[Dict[str, Any]] = None,
    file_name: Optional[str] = None,
    predictor: Any = None,
) -> Optional[str]:
    """一括ヘルパー: inferred_accounts ->（任意で Claude 分類）-> MF CSV 文字列。"""
    txs = extract_transactions_from_inferred_accounts(
        inferred_accounts=inferred_accounts,
        ocr_data=ocr_data,
        file_name=file_name,
    )
    if not txs:
        return None

    classify_transactions(txs, predictor=predictor)

    # 内部参照（_ref）は CSV に出さない
    for tx in txs:
        tx.pop("_ref", None)

    try:
        return MfExportService().generate_csv(txs)
    except Exception as e:
        logger.exception("MF CSV export failed: %s", e)
        return None


def build_mf_csv_from_transactions(txs: Sequence[Dict[str, Any]]) -> Optional[str]:
    """正規化済みの transactions から MF 仕訳帳 CSV を生成します。"""
    if not txs:
        return None

    clean: List[Dict[str, Any]] = []
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        copy_tx = dict(tx)
        copy_tx.pop("_ref", None)
        clean.append(copy_tx)

    try:
        return MfExportService().generate_csv(clean)
    except Exception as e:
        logger.exception("MF CSV export failed: %s", e)
        return None


def classify_transactions(
    txs: List[Dict[str, Any]],
    *,
    predictor: Any = None,
) -> List[Dict[str, Any]]:
    """best-effort の分類。

    `predictor` が未指定なら利用可能な `ClaudePredictor` を内部で解決し、
    利用不可なら no-op で返します。
    """

    if predictor is None:
        try:
            predictor = ClaudePredictor()
        except Exception as e:
            logger.debug("Claude predictor is unavailable; skip classification: %s", e)
            return txs

    return classify_transactions_with_claude(txs, predictor=predictor)


async def persist_transactions_to_db(
    *,
    db_pool: Any,
    tenant_id: str,
    invoice_id: Optional[str],
    classified_txs: Sequence[Dict[str, Any]],
    strict: bool = False,
) -> Tuple[int, List[str]]:
    """分類済み取引を `claude_predictions` と `mf_journal_entries` に保存します。

    DB 書き込みロジックを account_classifier 側に閉じ込め、他モジュールは pipeline 呼び出しだけで済むようにします。
    """
    if not classified_txs:
        return 0, []
    if db_pool is None:
        raise ValueError("db_pool is required when persist_db=True")
    if not tenant_id:
        raise ValueError("tenant_id is required when persist_db=True")

    from app.account_classifier.db_service import (
        ClaudePredictionService,
        MfJournalEntryService,
        convert_transaction_to_mf_journal_fields,
    )

    claude_service = ClaudePredictionService(db_pool)
    mf_service = MfJournalEntryService(db_pool)

    saved = 0
    errors: List[str] = []
    entry_ids: List[str] = []
    for idx, tx in enumerate(classified_txs, 1):
        try:
            direction = (tx.get("direction") or "expense").lower()
            predicted_account = tx.get("accountName") or ("雑費" if direction == "expense" else "売上高")

            account_confidence = tx.get("account_confidence")
            if account_confidence is None:
                account_confidence = tx.get("confidence")

            raw_response = tx.get("raw_response") or tx.get("claude_raw_response")
            if raw_response is None:
                # Store the full incoming classified payload for audit/debug.
                if invoice_id:
                    raw_response = json.dumps({"invoice_id": invoice_id, "transaction": tx}, ensure_ascii=False)
                else:
                    raw_response = json.dumps(tx, ensure_ascii=False)

            prediction_id = await claude_service.save_prediction(
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                input_vendor=str(tx.get("vendor") or ""),
                input_description=str(tx.get("description") or ""),
                input_amount=float(tx.get("amount") or 0),
                input_direction=direction,
                predicted_account=str(predicted_account),
                account_confidence=float(account_confidence or 0),
                reasoning=tx.get("reasoning"),
                matched_vendor_id=tx.get("matched_vendor_id"),
                matched_vendor_code=tx.get("matched_vendor_code"),
                matched_vendor_name=tx.get("matched_vendor_name"),
                vendor_confidence=tx.get("vendor_confidence"),
                matched_account_id=tx.get("matched_account_id"),
                matched_account_code=tx.get("matched_account_code"),
                matched_account_name=tx.get("matched_account_name"),
                claude_model=str(tx.get("claude_model") or "dify"),
                tokens_used=tx.get("claude_tokens_used"),
                raw_response=str(raw_response) if raw_response is not None else None,
                status=str(tx.get("status") or "completed"),
                error_message=tx.get("error_message"),
            )

            journal_fields = convert_transaction_to_mf_journal_fields(tx)
            entry_id = await mf_service.save_journal_entry(
                tenant_id=tenant_id,
                claude_prediction_id=prediction_id or None,
                transaction_date=journal_fields.get("transaction_date"),
                transaction_type=str(journal_fields.get("transaction_type") or direction),
                income_amount=journal_fields.get("income_amount"),
                expense_amount=journal_fields.get("expense_amount"),
                account_subject=str(journal_fields.get("account_subject") or predicted_account),
                matched_account_id=journal_fields.get("matched_account_id"),
                matched_account_code=journal_fields.get("matched_account_code"),
                vendor=journal_fields.get("vendor"),
                matched_vendor_id=journal_fields.get("matched_vendor_id"),
                matched_vendor_code=journal_fields.get("matched_vendor_code"),
                description=journal_fields.get("description"),
                account_book=journal_fields.get("account_book"),
                tax_category=journal_fields.get("tax_category"),
                memo=journal_fields.get("memo"),
                tag_names=journal_fields.get("tag_names"),
                status=str(tx.get("journal_status") or "draft"),
                error_message=tx.get("journal_error_message"),
            )
            if entry_id:
                entry_ids.append(entry_id)
            saved += 1
        except Exception as e:
            logger.error("Failed to persist tx %s: %s", idx, e, exc_info=True)
            errors.append(f"tx={idx}: {e}")
            continue

    if strict and errors:
        raise RuntimeError(f"Persist failed for {len(errors)}/{len(classified_txs)} transactions. First error: {errors[0]}")

    return saved, entry_ids


async def run_account_classifier(
    *,
    inferred_accounts: Optional[List[Dict[str, Any]]] = None,
    ocr_data: Optional[Dict[str, Any]] = None,
    file_name: Optional[str] = None,
    transactions: Optional[List[Dict[str, Any]]] = None,
    predictor: Any = None,
    generate_mf_csv: bool = True,
    persist_db: bool = False,
    db_pool: Any = None,
    tenant_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
) -> AccountClassifierPipelineResult:
    """単一エントリポイント: 正規化 -> 分類 -> (任意)CSV生成 -> (任意)DB保存。

    他のモジュールは個別の helper を直接呼ばず、基本的にこの関数だけを呼び出します。

    入力は次のどちらかを指定します:
    - `inferred_accounts` (+ 任意で `ocr_data` / `file_name`)
    - `transactions`（すでに正規化済みの取引リスト）

    Args:
        inferred_accounts: OCR/推論の結果（inferred_accounts）をそのまま渡します。
            `extract_transactions_from_inferred_accounts()` により取引（transactions）へ正規化されます。
            `transactions` を指定した場合は無視されます。
        ocr_data: OCR の補助情報（例: ページ情報、抽出メタデータ等）。
            正規化処理で vendor/date などの補完に使われることがあります。
        file_name: 元ファイル名（例: アップロードされた PDF/画像名）。
            正規化時の補助情報として使われることがあります。
        transactions: すでに正規化済みの取引リスト（dict の配列）。
            これを指定すると `inferred_accounts` からの正規化は行いません。
        predictor: 分類器（例: ClaudePredictor）。
            未指定の場合は利用可能なら内部で初期化し、利用不可なら分類をスキップします（best-effort）。
        generate_mf_csv: True の場合、分類後の取引から MF 仕訳帳形式の CSV テキストを生成します。
        persist_db: True の場合、分類結果を DB（claude_predictions / mf_journal_entries）へ保存します。
            保存には `db_pool` と `tenant_id` が必須です。
        db_pool: asyncpg Pool 等の DB 接続プール。`persist_db=True` のときのみ使用します。
        tenant_id: テナントID（RLS/テナント分離のため必須）。`persist_db=True` のとき必須です。
        invoice_id: 紐づける請求書ID（任意）。保存時に `claude_predictions.invoice_id` として使われます。

    Returns:
        AccountClassifierPipelineResult: `transactions`（分類結果を含む）、`mf_csv`、`persisted_count`、`errors`。
    """

    errors: List[str] = []

    if transactions is None:
        transactions = extract_transactions_from_inferred_accounts(
            inferred_accounts=inferred_accounts,
            ocr_data=ocr_data,
            file_name=file_name,
        )
    else:
        # 呼び出し側のリストを想定外に破壊しないよう、dict のみを抽出して扱う
        transactions = [tx for tx in transactions if isinstance(tx, dict)]

    transactions = normalize_transactions(transactions)

    if not transactions:
        return AccountClassifierPipelineResult(transactions=[], mf_csv=None, persisted_count=0, errors=[])

    try:
        classify_transactions(transactions, predictor=predictor)
    except Exception as e:
        logger.exception("Classification step failed")
        errors.append(f"classification_failed: {e}")

    mf_csv: Optional[str] = None
    if generate_mf_csv:
        mf_csv = build_mf_csv_from_transactions(transactions)

    persisted_count = 0
    persisted_entry_ids: List[str] = []
    if persist_db:
        try:
            persisted_count, persisted_entry_ids = await persist_transactions_to_db(
                db_pool=db_pool,
                tenant_id=str(tenant_id or ""),
                invoice_id=invoice_id,
                classified_txs=transactions,
            )
        except Exception as e:
            logger.exception("DB persistence failed")
            errors.append(f"persist_failed: {e}")

    return AccountClassifierPipelineResult(
        transactions=transactions,
        mf_csv=mf_csv,
        persisted_count=persisted_count,
        persisted_entry_ids=persisted_entry_ids,
        errors=errors,
    )


def run_pipeline(
    *,
    ocr_jsonl_path: Path,
    mf_template_path: Optional[Path] = None,
    out_csv_path: Optional[Path] = None,
    predictor: str = "none",
) -> str:
    """/api/classify/batch-process 用の互換パイプライン。

    - 改行区切り JSON（JSONL）を読み込み、各行を transaction 風の dict として扱います。
    - MF 仕訳帳形式の CSV を生成します。

    注意:
    - `mf_template_path` は現在未使用です（後方互換のため引数だけ残しています）。
    - この関数は同期関数です。
    """

    if not ocr_jsonl_path.exists():
        raise FileNotFoundError(f"Input JSONL not found: {ocr_jsonl_path}")

    txs: List[Dict[str, Any]] = []
    with ocr_jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                txs.append(obj)

    if predictor in {"claude", "auto"}:
        try:
            classify_transactions(txs, predictor=None)
        except Exception:
            # best-effort
            pass
    csv_text = build_mf_csv_from_transactions(txs) or ""

    if out_csv_path is not None:
        out_csv_path.parent.mkdir(parents=True, exist_ok=True)
        # MF 系ツールは cp932 を期待することが多い
        out_csv_path.write_text(csv_text, encoding="cp932", errors="replace")

    return csv_text
