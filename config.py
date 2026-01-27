import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_KEY")

APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL")
