-- CreateTable
CREATE TABLE "accounts" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "provider_account_id" TEXT NOT NULL,
    "refresh_token" TEXT,
    "access_token" TEXT,
    "expires_at" INTEGER,
    "token_type" TEXT,
    "scope" TEXT,
    "id_token" TEXT,
    "session_state" TEXT,

    CONSTRAINT "accounts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "session_token" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "expires" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app_users" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "email" TEXT NOT NULL,
    "email_verified" TIMESTAMP(3),
    "image" TEXT,
    "password" TEXT,
    "role" TEXT NOT NULL DEFAULT 'user',
    "tenant_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "app_users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "verification_tokens" (
    "identifier" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "expires" TIMESTAMP(3) NOT NULL
);

-- CreateTable
CREATE TABLE "tenants" (
    "id" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "country_code" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "tenants_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_files" (
    "id" TEXT NOT NULL,
    "dify_id" TEXT NOT NULL,
    "file_url" TEXT,
    "file_name" TEXT,
    "file_size" INTEGER,
    "mime_type" TEXT,
    "extracted_amount" DOUBLE PRECISION,
    "extracted_date" TIMESTAMP(3),
    "status" TEXT DEFAULT 'pending',
    "error_message" TEXT,
    "processed_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "tenant_id" TEXT,

    CONSTRAINT "chat_files_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_results" (
    "id" TEXT NOT NULL,
    "chat_file_id" TEXT NOT NULL,
    "result" JSONB NOT NULL,
    "status" TEXT DEFAULT 'processing',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ai_results_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ocr_results" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT,
    "chat_file_id" TEXT,
    "file_name" TEXT NOT NULL,
    "ocr_result" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION DEFAULT 0.0,
    "status" TEXT DEFAULT 'processing',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ocr_results_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "reconciliations" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT,
    "chat_file_id" TEXT,
    "journal_entry_id" TEXT NOT NULL,
    "status" TEXT DEFAULT 'pending',
    "notes" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "reconciliations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "journal_entries" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "date" TIMESTAMP(3) NOT NULL,
    "description" TEXT NOT NULL,
    "debit_account" TEXT NOT NULL,
    "credit_account" TEXT NOT NULL,
    "amount" DOUBLE PRECISION NOT NULL,
    "currency" TEXT DEFAULT 'JPY',
    "reference" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "journal_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "claude_predictions" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT,
    "chat_file_id" TEXT,
    "input_vendor" TEXT NOT NULL,
    "input_description" TEXT NOT NULL,
    "input_amount" DOUBLE PRECISION NOT NULL,
    "input_direction" TEXT NOT NULL,
    "predicted_account" TEXT NOT NULL,
    "account_confidence" DOUBLE PRECISION NOT NULL,
    "reasoning" TEXT,
    "matched_vendor_id" TEXT,
    "matched_vendor_code" TEXT,
    "matched_vendor_name" TEXT,
    "vendor_confidence" DOUBLE PRECISION,
    "matched_account_id" TEXT,
    "matched_account_code" TEXT,
    "matched_account_name" TEXT,
    "claude_model" TEXT NOT NULL,
    "tokens_used" INTEGER,
    "raw_response" TEXT,
    "status" TEXT NOT NULL DEFAULT 'completed',
    "error_message" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "claude_predictions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "mf_journal_entries" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "claude_prediction_id" TEXT,
    "transaction_date" TIMESTAMP(3) NOT NULL,
    "transaction_type" TEXT NOT NULL,
    "income_amount" DOUBLE PRECISION,
    "expense_amount" DOUBLE PRECISION,
    "account_subject" TEXT NOT NULL,
    "matched_account_id" TEXT,
    "matched_account_code" TEXT,
    "vendor" TEXT,
    "matched_vendor_id" TEXT,
    "matched_vendor_code" TEXT,
    "description" TEXT,
    "account_book" TEXT,
    "tax_category" TEXT,
    "memo" TEXT,
    "tag_names" TEXT,
    "csv_exported" BOOLEAN NOT NULL DEFAULT false,
    "csv_exported_at" TIMESTAMP(3),
    "mf_imported" BOOLEAN NOT NULL DEFAULT false,
    "mf_imported_at" TIMESTAMP(3),
    "mf_journal_id" TEXT,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "error_message" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "mf_journal_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_sessions" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "dify_id" TEXT NOT NULL,
    "title" TEXT,
    "is_pinned" BOOLEAN NOT NULL DEFAULT false,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "chat_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "accounts_provider_provider_account_id_key" ON "accounts"("provider", "provider_account_id");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_session_token_key" ON "sessions"("session_token");

-- CreateIndex
CREATE UNIQUE INDEX "app_users_email_key" ON "app_users"("email");

-- CreateIndex
CREATE UNIQUE INDEX "verification_tokens_token_key" ON "verification_tokens"("token");

-- CreateIndex
CREATE UNIQUE INDEX "verification_tokens_identifier_token_key" ON "verification_tokens"("identifier", "token");

-- CreateIndex
CREATE UNIQUE INDEX "tenants_code_key" ON "tenants"("code");

-- CreateIndex
CREATE INDEX "chat_files_dify_id_idx" ON "chat_files"("dify_id");

-- CreateIndex
CREATE INDEX "chat_files_status_idx" ON "chat_files"("status");

-- CreateIndex
CREATE INDEX "claude_predictions_tenant_id_created_at_idx" ON "claude_predictions"("tenant_id", "created_at");

-- CreateIndex
CREATE INDEX "claude_predictions_chat_file_id_idx" ON "claude_predictions"("chat_file_id");

-- CreateIndex
CREATE INDEX "claude_predictions_status_idx" ON "claude_predictions"("status");

-- CreateIndex
CREATE INDEX "mf_journal_entries_tenant_id_transaction_date_idx" ON "mf_journal_entries"("tenant_id", "transaction_date");

-- CreateIndex
CREATE INDEX "mf_journal_entries_status_idx" ON "mf_journal_entries"("status");

-- CreateIndex
CREATE INDEX "mf_journal_entries_csv_exported_idx" ON "mf_journal_entries"("csv_exported");

-- CreateIndex
CREATE INDEX "mf_journal_entries_mf_imported_idx" ON "mf_journal_entries"("mf_imported");

-- CreateIndex
CREATE INDEX "chat_sessions_user_id_updated_at_idx" ON "chat_sessions"("user_id", "updated_at");

-- CreateIndex
CREATE UNIQUE INDEX "chat_sessions_dify_id_key" ON "chat_sessions"("dify_id");

-- AddForeignKey
ALTER TABLE "accounts" ADD CONSTRAINT "accounts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app_users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app_users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "app_users" ADD CONSTRAINT "app_users_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_files" ADD CONSTRAINT "chat_files_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_files" ADD CONSTRAINT "chat_files_dify_id_fkey" FOREIGN KEY ("dify_id") REFERENCES "chat_sessions"("dify_id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_results" ADD CONSTRAINT "ai_results_chat_file_id_fkey" FOREIGN KEY ("chat_file_id") REFERENCES "chat_files"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ocr_results" ADD CONSTRAINT "ocr_results_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ocr_results" ADD CONSTRAINT "ocr_results_chat_file_id_fkey" FOREIGN KEY ("chat_file_id") REFERENCES "chat_files"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "reconciliations" ADD CONSTRAINT "reconciliations_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "reconciliations" ADD CONSTRAINT "reconciliations_chat_file_id_fkey" FOREIGN KEY ("chat_file_id") REFERENCES "chat_files"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "reconciliations" ADD CONSTRAINT "reconciliations_journal_entry_id_fkey" FOREIGN KEY ("journal_entry_id") REFERENCES "journal_entries"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "journal_entries" ADD CONSTRAINT "journal_entries_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claude_predictions" ADD CONSTRAINT "claude_predictions_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claude_predictions" ADD CONSTRAINT "claude_predictions_chat_file_id_fkey" FOREIGN KEY ("chat_file_id") REFERENCES "chat_files"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "mf_journal_entries" ADD CONSTRAINT "mf_journal_entries_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_sessions" ADD CONSTRAINT "chat_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "app_users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
