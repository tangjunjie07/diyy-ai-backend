

## OCR登録API サンプルcurl（multipart/form-data）
```sh
curl -X POST http://localhost:8000/analyze/invoice \
   -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdXBlcmFkbWluQGV4YW1wbGUuY29tIiwicm9sZSI6InN1cGVyX2FkbWluIiwidXNlcl9pZCI6ImNta242eHY0ZTAwMDAwdmo2MDh3YXdrbDEifQ.ejuCl2Er70_6TCyOcV9YBXtnh824NjOhVXsVGvPYpLs" \
   -F "userId=cmknaf2a60002q7j64u1qzo29" \
   -F "difyId=d94f1049-1d89-4839-9af5-956b43425430" \
   -F "tenantId=cmknae8ra0000q7j6ay572od3" \
   -F "files=@/Users/junjietang/Projects/dify-ai-backend/test-data/株式会社ブリッジワールドコンサルティング御中_請求書_INV-106002485.pdf"
```

## AI登録API サンプルcurl（application/json）
```sh
curl -X POST http://localhost:8000/ai/result \
   -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdXBlcmFkbWluQGV4YW1wbGUuY29tIiwicm9sZSI6InN1cGVyX2FkbWluIiwidXNlcl9pZCI6ImNta242eHY0ZTAwMDAwdmo2MDh3YXdrbDEifQ.ejuCl2Er70_6TCyOcV9YBXtnh824NjOhVXsVGvPYpLs" \
   -H "Content-Type: application/json" \
   -d '{
      "tenantId": "cmknae8ra0000q7j6ay572od3",
      "json_text": "[{\"chatFileId\": \"cmknfj9ns0001aruejainwyqk\", \"totalAmount\": 7575, \"invoiceDate\": \"2025-12-30\", \"currency\": \"JPY\", \"projectId\": \"プロジェクトコード\", \"accounting\": [{\"accountItem\": \"外注費\", \"subAccountItem\": \"協力会社への業務委託\", \"amount\": 7575, \"date\": \"2025-12-30\", \"confidence\": 0.6, \"reasoning\": \"フルーツみかみが業務委託先と考えられるため外注費に分類したが、詳細な内容が不明なため信頼度は低い。\", \"is_anomaly\": false}], \"summary\": \"フルーツみかみへの支払いに関する領収書。内容の詳細は不明のため、外注費として計上。\", \"filename\": \"PHOTO-2026-01-06-12-07-03.jpg\"}]"
   }'
```

### トークン発行（ログイン）
```
curl -X POST http://localhost:8000/auth/token \
	-H "Content-Type: application/json" \
	-d '{"email":"superadmin@example.com","password":"superadmin1234"}'
```

### トークン検証（認証済みステータス取得）
```
curl -X GET http://localhost:8000/status \
	-H "Authorization: Bearer <発行されたトークン>"
```
## Python仮想環境（venv）セットアップ・利用ルール

開発・実行・パッケージインストール時は、必ずPython 3.12.7のvenvを有効化してからコマンドを実行してください。

例:
```

## 環境変数・設定値管理ルール

FastAPIプロジェクトで利用する環境変数や設定値（os.getenvで取得する値）は、必ず`config.py`にまとめて定義・管理してください。
### 初回セットアップ・再現手順
1. pyenvでPython 3.12.7を有効化
   ```sh
   pyenv local 3.12.7
   export PATH="$HOME/.pyenv/shims:$PATH"
   python --version  # 3.12.7 であることを確認
   ```
2. venv再構築＆パッケージインストール
   ```sh
   rm -rf .venv
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Prisma Pythonクライアント生成
   ```sh
   source .venv/bin/activate
   prisma generate
   ```
4. サーバー起動
   ```sh
   source .venv/bin/activate
   uvicorn main:app --reload
   ```

### venv有効化例
```
source .venv/bin/activate
python main.py
pip install -r requirements.txt
```


- 例: JWT_SECRET_KEY, JWT_ALGORITHM, AZURE_ENDPOINT, AZURE_KEY など
- 新たな環境変数や設定値が必要な場合は、`config.py`に追加し、各モジュールから `from config import ...` で参照してください。
- 直接os.getenvを各ファイルで呼ばず、必ずconfig.py経由で取得すること。
# config.py
import os
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_KEY")
```

```python
# 利用側
from config import SECRET_KEY, ALGORITHM, AZURE_ENDPOINT, AZURE_KEY
```
source .venv/bin/activate
python main.py
pip install -r requirements.txt
```
## Pythonパッケージ管理ルール

Pythonプロジェクトで新たにパッケージをインストールする場合は、必ず`requirements.txt`へ追加・反映してください。

- `pip install パッケージ名` でインストールした場合も、`requirements.txt`に追記すること。
- 依存パッケージのバージョン指定も必要に応じて明記すること。
- チームメンバーが環境を再現できるよう、`requirements.txt`が常に最新になるように管理してください。

例:
```
pip install requests
# → requirements.txt に requests を追記
```
