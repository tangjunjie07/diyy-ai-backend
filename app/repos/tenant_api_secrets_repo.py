"""テナント別 API シークレット取得（最小スタブ）。

本来は DB（RLS 等）でテナント分離されたシークレット管理を行う想定ですが、
この dify-ai-backend では軽量に保つため、現時点では DB を参照せず、環境変数から
テナント別の API キーを取得します。

運用で DB 接続と実シークレットテーブルを用意できる場合は、このモジュールを
置き換えてください。

対応する環境変数（どちらも同じ値＝Anthropic API キーを返します）:
- `TENANT_API_KEY_ANTHROPIC_<TENANT_ID>`
- `ANTHROPIC_API_KEY_TENANT_<TENANT_ID>`
"""

from __future__ import annotations

import os
from typing import Any, Optional

PROVIDER_ANTHROPIC = "anthropic"


async def get_tenant_api_secret(
    _conn: Any,
    *,
    tenant_id: str,
    provider: str,
) -> Optional[str]:
    if provider != PROVIDER_ANTHROPIC:
        return None

    # provider/tenant を明示した命名を優先
    key = os.getenv(f"TENANT_API_KEY_ANTHROPIC_{tenant_id}")
    if key:
        return key

    # 後方互換の命名
    key = os.getenv(f"ANTHROPIC_API_KEY_TENANT_{tenant_id}")
    if key:
        return key

    return None
