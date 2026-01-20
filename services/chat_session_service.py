from prisma import Prisma

class ChatSessionService:
    def __init__(self):
        self.prisma = Prisma()

    async def ensure_session_exists(self, user_id: str, dify_id: str):
        await self.prisma.connect()
        session = await self.prisma.chatsession.find_first(where={"userId": user_id, "difyId": dify_id})
        if not session:
            await self.prisma.chatsession.create({
                "userId": user_id,
                "difyId": dify_id
            })
        await self.prisma.disconnect()

    async def register_chat_file(
        self,
        dify_id: str,
        tenant_id: str = None,
        file_name: str = None,
        file_url: str = None,
        file_size: int = None,
        mime_type: str = None,
        ocr_result: str = None,
        status: str = None,
        error_message: str = None
    ):
        await self.prisma.connect()
        data = {
            "difyId": dify_id,
            "fileName": file_name,
            "fileUrl": file_url,
            "fileSize": file_size,
            "mimeType": mime_type,
            "tenantId": tenant_id,
            "ocrResult": ocr_result,
            "status": status or "pending",
            "errorMessage": error_message
        }
        # Noneの値は除外
        data = {k: v for k, v in data.items() if v is not None}
        await self.prisma.chatfile.create(data)
        await self.prisma.disconnect()

chat_session_service = ChatSessionService()
