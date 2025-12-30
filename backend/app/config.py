from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str

    # Anthropic Claude
    anthropic_api_key: str = ""

    # Neo4j
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # SEC EDGAR
    sec_user_agent: str = "InsightLookinsight contact@lookinsight.ai"

    # Redis (for Celery task queue)
    redis_url: str = "redis://localhost:6379/0"

    # App settings
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
