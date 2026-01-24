from __future__ import annotations

from typing import Any, Optional


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def normalize_confidence_ratio(value: Any) -> Optional[float]:
    """Normalize a confidence-like input into a 0..1 ratio.

    Accepts:
    - 0..1 ratio
    - 0..100 percentage
    - strings/ints/floats (best-effort)

    Returns None if not parseable.
    """

    num = _to_float(value)
    if num is None:
        return None

    # Heuristic: if >1, treat as percent.
    ratio = num / 100.0 if num > 1.0 else num

    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    return ratio


def format_confidence_percent(value: Any) -> Optional[str]:
    """Format a confidence-like input into a human readable percent string."""

    ratio = normalize_confidence_ratio(value)
    if ratio is None:
        return None

    percent = ratio * 100.0
    # Prefer whole percent when possible.
    if abs(percent - round(percent)) < 1e-6:
        return f"{percent:.0f}%"
    return f"{percent:.1f}%"


def build_journal_memo(*, reason: Any, account_confidence: Any, vendor_confidence: Any) -> Optional[str]:
    """Build MF "仕訳メモ" / DB memo text.

    - `reason`: Claude reasoning/analysis text (optional)
    - confidences: account/vendor confidence (optional)

    Output examples:
    - "理由... (conf: acc=87%, vendor=65%)"
    - "conf: acc=87%"
    - None (when both reason and confidences are empty)
    """

    memo_reason: Optional[str]
    if isinstance(reason, str):
        memo_reason = reason.strip() or None
    else:
        memo_reason = None

    parts = []
    acc = format_confidence_percent(account_confidence)
    if acc:
        parts.append(f"acc={acc}")

    vendor = format_confidence_percent(vendor_confidence)
    if vendor:
        parts.append(f"vendor={vendor}")

    if not memo_reason and not parts:
        return None

    if parts:
        conf_display = ", ".join(parts)
        if memo_reason:
            return f"{memo_reason} (conf: {conf_display})"
        return f"conf: {conf_display}"

    return memo_reason
