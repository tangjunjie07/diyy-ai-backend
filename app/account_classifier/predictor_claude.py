"""
Claude 3.5 Sonnetを使った勘定科目予測器

Copied from:
- ai-business-automation/services/ingestion-service/app/account_classifier/predictor_claude.py

Notes for dify-ai-backend:
- Keep API keys server-side. Do NOT expose keys to clients.
- By default reads `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY`.
- Model can be overridden via `ANTHROPIC_MODEL`.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AccountPrediction:
    """勘定科目（マスタ照合）+ 取引先マスタ照合の予測結果"""

    account: str
    confidence: float
    reasoning: Optional[str] = None

    # Claude が要約/整形した摘要（任意）。DB保存やMF連携に使う。
    description: Optional[str] = None

    matched_account_code: Optional[str] = None
    matched_account_name: Optional[str] = None
    account_confidence: Optional[float] = None

    matched_vendor_id: Optional[str] = None
    matched_vendor_name: Optional[str] = None
    vendor_confidence: Optional[float] = None

    raw_response: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None


@dataclass
class ClaudePredictor:
    """Claude を使った勘定科目予測器（best-effort）"""

    api_key: Optional[str] = None
    model: str = "claude-3-5-sonnet-latest"
    max_tokens: int = 500
    temperature: float = 0.0

    def __post_init__(self):
        if self.api_key is None:
            # Prefer Anthropic naming; keep backward compatibility with older docs.
            self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Anthropic API key is required. Set `ANTHROPIC_API_KEY` (recommended) or `CLAUDE_API_KEY`."
            )

        self.model = os.getenv("ANTHROPIC_MODEL", self.model)

        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("Anthropic library is required. Install with: pip install anthropic") from e

        self.client = Anthropic(api_key=self.api_key)
        logger.info("Claude predictor initialized with model=%s", self.model)

    def predict(
        self,
        vendor: str,
        description: str,
        amount: float,
        direction: str,
        *,
        vendor_masters: Optional[List[Dict[str, Any]]] = None,
        account_masters: Optional[List[Dict[str, Any]]] = None,
    ) -> AccountPrediction:
        vendor_candidates = self._select_vendor_candidates(vendor, vendor_masters=vendor_masters)
        account_candidates = self._select_account_candidates(
            vendor=vendor,
            description=description,
            direction=direction,
            account_masters=account_masters,
        )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            vendor,
            description,
            amount,
            direction,
            vendor_candidates,
            account_candidates,
        )

        logger.info(
            "🔥 Calling Claude API model=%s vendor=%s amount=%s direction=%s",
            self.model,
            vendor,
            amount,
            direction,
        )

        used_model = self.model
        response = self.client.messages.create(
            model=used_model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        tokens_used: Optional[int] = None
        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                in_toks = getattr(usage, "input_tokens", None)
                out_toks = getattr(usage, "output_tokens", None)
                if isinstance(in_toks, int) or isinstance(out_toks, int):
                    tokens_used = int((in_toks or 0) + (out_toks or 0))
        except Exception:
            tokens_used = None

        content = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                content += block.text
        content = content.strip()

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        raw_response = content

        try:
            result = json.loads(content)
        except Exception as e:
            logger.exception("Failed to parse Claude response: %s", e)
            fallback = self._fallback_prediction(direction)
            fallback.raw_response = raw_response
            fallback.model = used_model
            fallback.tokens_used = tokens_used
            return fallback

        account = str(result.get("account") or "")
        confidence = float(result.get("confidence") or 0.5)
        reasoning = result.get("reasoning") or ""
        description = result.get("description") or result.get("normalized_description") or None

        matched_account_code: Optional[str] = None
        matched_account_name: Optional[str] = None
        account_confidence: Optional[float] = None

        account_match = result.get("account_match")
        if isinstance(account_match, dict):
            matched_account_code = account_match.get("code")
            matched_account_name = account_match.get("name")
            if account_match.get("confidence") is not None:
                try:
                    account_confidence = float(account_match.get("confidence"))
                except Exception:
                    account_confidence = None

        if not matched_account_name:
            matched_account_name = result.get("matched_account_name") or result.get("matchedAccountName")
        if not matched_account_code:
            matched_account_code = result.get("matched_account_code") or result.get("matchedAccountCode")
        if account_confidence is None:
            if result.get("account_confidence") is not None:
                try:
                    account_confidence = float(result.get("account_confidence"))
                except Exception:
                    account_confidence = None
            elif result.get("accountConfidence") is not None:
                try:
                    account_confidence = float(result.get("accountConfidence"))
                except Exception:
                    account_confidence = None

        if matched_account_name:
            account = str(matched_account_name)
            if account_confidence is not None:
                confidence = float(account_confidence)

        matched_vendor_id: Optional[str] = None
        matched_vendor_name: Optional[str] = None
        vendor_confidence: Optional[float] = None

        vendor_match = result.get("vendor_match")
        if isinstance(vendor_match, dict):
            matched_vendor_id = vendor_match.get("id")
            matched_vendor_name = vendor_match.get("name")
            if vendor_match.get("confidence") is not None:
                try:
                    vendor_confidence = float(vendor_match.get("confidence"))
                except Exception:
                    vendor_confidence = None
        else:
            matched_vendor_id = result.get("matched_vendor_id") or result.get("matchedVendorId")
            matched_vendor_name = result.get("matched_vendor_name") or result.get("matchedVendorName")
            if result.get("vendor_confidence") is not None:
                try:
                    vendor_confidence = float(result.get("vendor_confidence"))
                except Exception:
                    vendor_confidence = None
            elif result.get("vendorConfidence") is not None:
                try:
                    vendor_confidence = float(result.get("vendorConfidence"))
                except Exception:
                    vendor_confidence = None

        # Validate/normalize with master candidates (best-effort)
        if account_masters:
            account = self._normalize_account_name(account, account_masters=account_masters, direction=direction)

        return AccountPrediction(
            account=account,
            confidence=float(confidence),
            reasoning=str(reasoning) if reasoning is not None else None,
            description=str(description) if description is not None and str(description).strip() else None,
            matched_account_code=str(matched_account_code) if matched_account_code else None,
            matched_account_name=str(matched_account_name) if matched_account_name else None,
            account_confidence=float(account_confidence) if account_confidence is not None else None,
            matched_vendor_id=str(matched_vendor_id) if matched_vendor_id else None,
            matched_vendor_name=str(matched_vendor_name) if matched_vendor_name else None,
            vendor_confidence=float(vendor_confidence) if vendor_confidence is not None else None,
            raw_response=raw_response,
            model=used_model,
            tokens_used=tokens_used,
        )

    def _fallback_prediction(self, direction: str) -> AccountPrediction:
        direction_l = (direction or "expense").lower()
        account = "雑費" if direction_l == "expense" else "売上高"
        return AccountPrediction(account=account, confidence=0.0, reasoning="fallback")

    def _build_system_prompt(self) -> str:
        return (
            "You are a Japanese accounting assistant. "
            "Classify transactions into appropriate Japanese account subjects (勘定科目). "
            "You must return a single JSON object only. "
            "Also produce a short Japanese description for the journal entry (摘要)."
        )

    def _build_user_prompt(
        self,
        vendor: str,
        description: str,
        amount: float,
        direction: str,
        vendor_candidates: List[Dict[str, Any]],
        account_candidates: List[Dict[str, Any]],
    ) -> str:
        payload = {
            "vendor": vendor,
            "description": description,
            "amount": amount,
            "direction": direction,
            "vendor_candidates": vendor_candidates,
            "account_candidates": account_candidates,
            "response_schema": {
                "account": "string (account subject name)",
                "description": "string (short Japanese 摘要; do not include file name)",
                "confidence": "number 0..1",
                "reasoning": "string",
                "account_match": {"code": "string?", "name": "string?", "confidence": "number?"},
                "vendor_match": {"id": "string?", "name": "string?", "confidence": "number?"},
            },
        }
        return (
            "Classify the transaction and match to masters when possible. "
            "Return JSON only, no markdown.\n\n" + json.dumps(payload, ensure_ascii=False)
        )

    def _select_vendor_candidates(
        self,
        vendor: str,
        *,
        vendor_masters: Optional[List[Dict[str, Any]]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not vendor_masters:
            return []

        vendor = (vendor or "").strip()
        if not vendor:
            return vendor_masters[:limit]

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for v in vendor_masters:
            name = str(v.get("name") or "")
            score = difflib.SequenceMatcher(a=vendor, b=name).ratio()
            if vendor in name or name in vendor:
                score += 0.2
            scored.append((score, v))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [v for _, v in scored[:limit]]

    def _select_account_candidates(
        self,
        *,
        vendor: str,
        description: str,
        direction: str,
        account_masters: Optional[List[Dict[str, Any]]],
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        if not account_masters:
            return []

        direction_l = (direction or "expense").lower()
        candidates = []
        for a in account_masters:
            # Some masters may have a direction/type field; keep best-effort.
            try:
                t = str(a.get("type") or a.get("direction") or "").lower()
                if t and direction_l and direction_l not in t:
                    continue
            except Exception:
                pass
            candidates.append(a)

        # Very light keyword boost
        text = f"{vendor} {description}".strip()
        if not text:
            return candidates[:limit]

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for a in candidates:
            name = str(a.get("name") or "")
            score = difflib.SequenceMatcher(a=text, b=name).ratio()
            if name and name in text:
                score += 0.2
            scored.append((score, a))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:limit]]

    def _normalize_account_name(
        self,
        account: str,
        *,
        account_masters: List[Dict[str, Any]],
        direction: str,
    ) -> str:
        account = (account or "").strip()
        if not account:
            return "雑費" if (direction or "expense").lower() == "expense" else "売上高"

        names = [str(a.get("name") or "") for a in account_masters]
        if account in names:
            return account

        # Fuzzy match
        best = difflib.get_close_matches(account, names, n=1, cutoff=0.7)
        if best:
            return best[0]

        # Strip common decorations
        cleaned = re.sub(r"\s+", " ", account)
        best2 = difflib.get_close_matches(cleaned, names, n=1, cutoff=0.7)
        if best2:
            return best2[0]

        return account
