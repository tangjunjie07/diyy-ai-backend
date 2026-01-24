"""柔軟な OCR ローダー（正規化ユーティリティ）。

元ファイル: services/ingestion-service/app/account_classifier/flexible_ocr_loader.py

OCR 結果や推論結果など、入力の形が揃っていないデータを
account_classifier が扱える「transactions（取引）」の dict 配列へ正規化します。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.account_classifier.transaction import normalize_transaction_dict


def _infer_vendor_from_summary(summary: str) -> str:
    text = (summary or "").strip()
    if not text:
        return ""

    # 「フルーツみかみへの支払い…」のような日本語要約から取引先を推定する簡易ヒューリスティック。
    patterns = [
        r"^(.+?)への",
        r"^(.+?)から",
        r"^(.+?)に対する",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return (m.group(1) or "").strip()
    return ""


def extract_transactions_from_pending_journal_data(*, pending_journal_data: Any) -> List[Dict[str, Any]]:
    """Dify の出力ペイロードを transactions（取引）に正規化します。

    期待する例（Dify から）:
    {
        "pending_journal_data": "[{...}]"   # JSON 配列が文字列として渡されることが多い
    }

    各要素に含まれうるキー:
        - totalAmount, invoiceDate, currency, projectId, summary, filename
        - accounting: [{ accountItem, subAccountItem, amount, date, confidence, reasoning, is_anomaly }]
    """

    if pending_journal_data is None:
        return []

    # {"pending_journal_data": "[...]"} のようなラッパー形式も受け付ける
    if isinstance(pending_journal_data, dict) and "pending_journal_data" in pending_journal_data:
        return extract_transactions_from_pending_journal_data(
            pending_journal_data=pending_journal_data.get("pending_journal_data")
        )

    # Dify は JSON を文字列として送ることがある
    if isinstance(pending_journal_data, str):
        try:
            pending_journal_data = json.loads(pending_journal_data)
        except Exception:
            return []

    if isinstance(pending_journal_data, list):
        items = pending_journal_data
    elif isinstance(pending_journal_data, dict):
        items = [pending_journal_data]
    else:
        return []

    txs: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        total_amount = item.get("totalAmount")
        invoice_date = item.get("invoiceDate") or item.get("date")
        currency = item.get("currency")
        project_id = item.get("projectId")
        summary = item.get("summary") or item.get("description") or ""
        file_name = item.get("filename") or item.get("fileName") or ""

        vendor = item.get("vendor") or _infer_vendor_from_summary(str(summary))

        accounting = item.get("accounting")
        if isinstance(accounting, str):
            try:
                accounting = json.loads(accounting)
            except Exception:
                accounting = None

        if isinstance(accounting, list) and accounting:
            for acc in accounting:
                if not isinstance(acc, dict):
                    continue

                amount = acc.get("amount")
                if amount is None:
                    amount = total_amount

                date = acc.get("date") or invoice_date or ""

                # Dify は accountItem/subAccountItem を使うが、MF エクスポータ側は accountName を期待する
                account_name = acc.get("accountItem") or acc.get("accountName") or ""
                sub_account_item = acc.get("subAccountItem")

                direction = acc.get("direction") or item.get("direction")
                if not direction:
                    # 多くの請求書は支出。金額が負なら収入として扱う
                    try:
                        direction = "income" if float(amount or 0) < 0 else "expense"
                    except Exception:
                        direction = "expense"

                normalized = normalize_transaction_dict(
                    {
                        "date": date,
                        "vendor": vendor or "",
                        "description": acc.get("description") or summary or "",
                        "amount": amount or 0,
                        "direction": direction,
                        "accountName": account_name,
                        "subAccountItem": sub_account_item,
                        "confidence": acc.get("confidence"),
                        "reasoning": acc.get("reasoning"),
                        "is_anomaly": acc.get("is_anomaly"),
                        "currency": currency,
                        "projectId": project_id,
                        "fileName": file_name,
                        "_ref": acc,
                    }
                )
                if normalized is not None:
                    txs.append(normalized)
            continue

        # fallback: 単一取引として扱う
        direction = item.get("direction")
        if not direction:
            try:
                direction = "income" if float(total_amount or 0) < 0 else "expense"
            except Exception:
                direction = "expense"

        normalized = normalize_transaction_dict(
            {
                "date": invoice_date or "",
                "vendor": vendor or "",
                "description": summary or "",
                "amount": total_amount or 0,
                "direction": direction,
                "accountName": "",
                "currency": currency,
                "projectId": project_id,
                "fileName": file_name,
                "_ref": item,
            }
        )
        if normalized is not None:
            txs.append(normalized)

    return txs


def extract_transactions_from_inferred_accounts(
    *,
    inferred_accounts: Optional[List[Dict[str, Any]]],
    ocr_data: Optional[Dict[str, Any]] = None,
    file_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not inferred_accounts:
        return []

    txs: List[Dict[str, Any]] = []

    # ocr_data は任意。vendor/date などの補完に使う場合がある。
    vendor_default = None
    try:
        vendor_default = (ocr_data or {}).get("vendor")
    except Exception:
        vendor_default = None

    date_default = None
    try:
        date_default = (ocr_data or {}).get("date")
    except Exception:
        date_default = None

    for item in inferred_accounts:
        if not isinstance(item, dict):
            continue

        # すでに transaction っぽい形の場合はそのまま扱う
        if "amount" in item and ("direction" in item or "type" in item):
            direction = item.get("direction") or item.get("type") or "expense"
            normalized = normalize_transaction_dict(
                {
                    "date": item.get("date") or date_default or "",
                    "vendor": item.get("vendor") or vendor_default or "",
                    "description": item.get("description") or item.get("summary") or "",
                    "amount": item.get("amount") or 0,
                    "direction": direction,
                    "fileName": item.get("fileName") or file_name or "",
                    "_ref": item,
                }
            )
            if normalized is not None:
                txs.append(normalized)
            continue

        # ingestion-service 側の inferred_accounts 形式: {"items": [...]} 
        items = item.get("items")
        if isinstance(items, list) and items:
            for child in items:
                if not isinstance(child, dict):
                    continue
                direction = child.get("direction") or child.get("type") or item.get("direction") or "expense"
                normalized = normalize_transaction_dict(
                    {
                        "date": child.get("date") or item.get("date") or date_default or "",
                        "vendor": child.get("vendor") or item.get("vendor") or vendor_default or "",
                        "description": child.get("description") or child.get("summary") or item.get("description") or "",
                        "amount": child.get("amount") or 0,
                        "direction": direction,
                        "fileName": child.get("fileName") or item.get("fileName") or file_name or "",
                        "_ref": child,
                    }
                )
                if normalized is not None:
                    txs.append(normalized)
            continue

        # 最低限の fallback
        normalized = normalize_transaction_dict(
            {
                "date": item.get("date") or date_default or "",
                "vendor": item.get("vendor") or vendor_default or "",
                "description": item.get("description") or item.get("summary") or "",
                "amount": item.get("amount") or 0,
                "direction": item.get("direction") or "expense",
                "fileName": item.get("fileName") or file_name or "",
                "_ref": item,
            }
        )
        if normalized is not None:
            txs.append(normalized)

    return txs
