
import datetime
import asyncio
from prisma import Prisma

class ChatSessionService:
    def __init__(self):
        self.prisma = Prisma()
        try:
            # 起動時に一度だけconnect
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.prisma.connect())
            else:
                loop.run_until_complete(self.prisma.connect())
        except RuntimeError:
            # 新規イベントループが必要な場合
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.prisma.connect())

    async def register_chat_file_with_ocr_result(
        self,
        dify_id: str,
        tenant_id: str,
        file_name: str,
        file_size: int = None,
        mime_type: str = None,
        ocr_result_str: str = None,
        confidence: float = None,
        status: str = "completed"
    ):
        chat_file = await self.register_chat_file(
            dify_id=dify_id,
            tenant_id=tenant_id,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            status=status
        )
        await self.register_ocr_result(
            tenant_id=tenant_id,
            chat_file_id=chat_file.id if chat_file else None,
            file_name=file_name,
            ocr_result=ocr_result_str,
            confidence=confidence,
            status=status
        )
        return chat_file

    async def get_existing_ocr_result(self, tenant_id: str, file_name: str, file_size: int = None):
        # tenantId, fileName, fileSize一致のChatFile＋OcrResultを取得
        where = {
            "tenantId": tenant_id,
            "fileName": file_name,
        }
        if file_size is not None:
            where["fileSize"] = file_size
        chat_file = await self.prisma.chatfile.find_first(
            where=where,
            include={"ocrResults": True},
            order={"createdAt": "desc"}  # 最新のものを優先
        )
        if chat_file and chat_file.ocrResults and len(chat_file.ocrResults) > 0:
            return chat_file, chat_file.ocrResults[0]
        return None, None

    async def register_ai_result(self, chat_file_id: str, result, status: str = None):
        # 既存のAiResultを検索
        existing = await self.prisma.airesult.find_first(
            where={"chatFileId": chat_file_id}
        )
        data = {
            "result": result,
            "status": status or "processing"
        }
        if existing:
            # 更新
            return await self.prisma.airesult.update(
                where={"id": existing.id},
                data=data
            )
        else:
            # 新規作成
            data["chatFileId"] = chat_file_id
            return await self.prisma.airesult.create(data)

    async def update_chat_file(self, chat_file_id: str, tenant_id: str = None, extracted_amount: float = None, extracted_date = None, status: str = None):
        data = {}
        if tenant_id is not None:
            data["tenantId"] = tenant_id
        if extracted_amount is not None:
            data["extractedAmount"] = extracted_amount
        if extracted_date is not None:
            data["extractedDate"] = extracted_date
        if status is not None:
            data["status"] = status
        # updatedAtカラムが存在する場合は一緒に更新
        data["updatedAt"] = datetime.datetime.now(datetime.timezone.utc)
        await self.prisma.chatfile.update(
            where={"id": chat_file_id},
            data=data
        )

    async def ensure_session_exists(self, user_id: str, dify_id: str):
        session = await self.prisma.chatsession.find_first(where={"userId": user_id, "difyId": dify_id})
        if not session:
            await self.prisma.chatsession.create({
                "userId": user_id,
                "difyId": dify_id
            })

    async def register_chat_file(
        self,
        dify_id: str,
        tenant_id: str = None,
        file_name: str = None,
        file_url: str = None,
        file_size: int = None,
        mime_type: str = None,
        status: str = None,
        error_message: str = None
    ):
        import datetime
        data = {
            "difyId": dify_id,
            "fileName": file_name,
            "fileUrl": file_url,
            "fileSize": file_size,
            "mimeType": mime_type,
            "tenantId": tenant_id,
            "status": status or "pending",
            "errorMessage": error_message
        }
        if status == "completed":
            data["processedAt"] = datetime.datetime.now(datetime.timezone.utc)
        # Noneの値は除外
        data = {k: v for k, v in data.items() if v is not None}
        return await self.prisma.chatfile.create(data)


    async def register_ocr_result(
        self,
        tenant_id: str = None,
        chat_file_id: str = None,
        file_name: str = None,
        ocr_result: str = None,
        confidence: float = None,
        status: str = None
    ):
        # ocr_resultがオブジェクトの場合はdict等に変換してから渡すこと
        # 例: json.dumps(analyze_result.__dict__, ensure_ascii=False)
        data = {
            "tenantId": tenant_id,
            "chatFileId": chat_file_id,
            "fileName": file_name,
            "ocrResult": ocr_result,
            "confidence": confidence,
            "status": status or "processing"
        }
        # Noneの値は除外
        data = {k: v for k, v in data.items() if v is not None}
        await self.prisma.ocrresult.create(data)

chat_session_service = ChatSessionService()
