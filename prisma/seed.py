import asyncio
import os
from dotenv import load_dotenv
from prisma import Prisma
import bcrypt

load_dotenv('../../.env')

async def main():
    db = Prisma()
    await db.connect()

    # 1. 准备加密密码
    password = "superadmin123"
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    email = "superadmin@example.com"

    # 2. 模拟 upsert 逻辑 (先查后增)
    user = await db.user.find_unique(where={'email': email})

    if not user:
        new_user = await db.user.create(
            data={
                'email': email,
                'name': 'Super Administrator',
                'password': hashed_password,
                'role': 'super_admin',
                'tenantId': None,
            }
        )
        print(f"Seed data created: {new_user.name}")
    else:
        print("Super admin already exists, skipping...")

    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())