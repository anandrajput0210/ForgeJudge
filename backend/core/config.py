import os


class Settings:
    APP_NAME = os.getenv("APP_NAME", "ForgeJudge")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://forgejudge:forgejudge@localhost:5432/forgejudge",
    )
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "change-this-secret-in-production",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )


settings = Settings()