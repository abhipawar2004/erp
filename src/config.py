from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "mysql+asyncmy://root:password@localhost:3306/erp_db")

    class Config:
        env_file = ".env"


settings = Settings()
