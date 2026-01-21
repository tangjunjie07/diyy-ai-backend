# Dify AI Backend

## 概要

Dify AI Backend は、Azure Document Intelligence を使用した OCR 処理と AI 分析を組み合わせたバックエンドサービスです。Dify プラットフォームとの連携により、請求書や領収書のアップロード、OCR 処理、AI による自動仕訳分析を実現します。

## 主な機能

- **OCR 処理**: Azure Document Intelligence を使用して画像からテキストを抽出
- **AI 分析**: Claude AI を使用した自動仕訳分析
- **ファイル管理**: チャットセッションごとのファイル管理
- **マルチテナント対応**: テナントごとのデータ分離
- **認証**: JWT ベースの認証システム

## 技術スタック

- **バックエンド**: FastAPI (Python)
- **データベース**: PostgreSQL
- **ORM**: Prisma
- **OCR**: Azure Document Intelligence
- **AI**: Anthropic Claude
- **認証**: JWT
- **デプロイ**: 任意 (例: Docker, Vercel)

## インストール

### 前提条件

- Python 3.8+
- PostgreSQL
- Azure Document Intelligence アカウント
- Anthropic Claude API キー

### セットアップ

1. リポジトリをクローン:
   ```bash
   git clone https://github.com/your-repo/dify-ai-backend.git
   cd dify-ai-backend
   ```

2. 仮想環境を作成:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. 依存関係をインストール:
   ```bash
   pip install -r requirements.txt
   ```

4. Prisma をセットアップ:
   ```bash
   npx prisma generate
   npx prisma db push
   ```

5. 環境変数を設定:
   `.env` ファイルを作成し、以下の変数を設定:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   JWT_SECRET_KEY=your-secret-key
   AZURE_ENDPOINT=your-azure-endpoint
   AZURE_KEY=your-azure-key
   CLAUDE_API_KEY=your-claude-key
   ```

## 使用方法

### サーバーの起動

```bash
uvicorn main:app --reload
```

サーバーが `http://localhost:8000` で起動します。

### API エンドポイント

#### OCR 処理

- **POST /analyze/invoice**
  - 請求書画像をアップロードして OCR 処理を実行
  - パラメータ: `userId`, `difyId`, `tenantId`, `files`

#### AI 分析

- **POST /ai/result**
  - AI 分析結果を登録
  - パラメータ: `tenantId`, `json_text`

#### 認証

- **POST /auth/login** (例)
  - JWT トークンを取得

### 例: OCR 処理

```bash
curl -X POST http://localhost:8000/analyze/invoice \
  -H "Authorization: Bearer <token>" \
  -F "userId=user123" \
  -F "difyId=session123" \
  -F "tenantId=tenant123" \
  -F "files=@invoice.jpg"
```

### 例: AI 分析結果登録

```bash
curl -X POST http://localhost:8000/ai/result \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenantId": "tenant123",
    "json_text": "[{\"chatFileId\": \"file123\", \"totalAmount\": 1000, ...}]"
  }'
```

## データベーススキーマ

Prisma を使用したスキーマ定義 (`prisma/schema.prisma`) を参照してください。主要なモデル:

- `User`: ユーザー情報
- `Tenant`: テナント情報
- `ChatSession`: Dify チャットセッション
- `ChatFile`: アップロードファイル
- `OcrResult`: OCR 処理結果
- `AiResult`: AI 分析結果

## 開発

### テスト

```bash
pytest
```

### コードフォーマット

```bash
black .
```

## ライセンス

MIT License

## 貢献

プルリクエストやイシューを歓迎します。開発前に CONTRIBUTING.md をお読みください。

## 連絡先

質問やフィードバックは GitHub Issues までお願いします。