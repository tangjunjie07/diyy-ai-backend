"""Master data loader for account_classifier.

Copied from services/ingestion-service/app/account_classifier/master_loader.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MasterLoader:
    base_dir: Path

    def load_account_masters(self) -> List[Dict[str, Any]]:
        path = self.base_dir / "masters" / "account_masters.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("account_masters.json must be a list")
        return data

    def load_vendor_masters(self, *, active_only: bool = False) -> List[Dict[str, Any]]:
        path = self.base_dir / "masters" / "vendor_masters.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("vendor_masters.json must be a list")
        if not active_only:
            return data
        out: List[Dict[str, Any]] = []
        for v in data:
            try:
                if v.get("active") is False:
                    continue
            except Exception:
                pass
            out.append(v)
        return out


@lru_cache(maxsize=1)
def get_master_loader(base_dir: Optional[Path] = None) -> MasterLoader:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent
    return MasterLoader(base_dir=base_dir)
