## APIトークン発行・検証用curlコマンド例

### トークン発行（ログイン）
```
curl -X POST http://localhost:8000/auth/token \
	-H "Content-Type: application/json" \
	-d '{"email":"your_superadmin_email","password":"your_password"}'
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
