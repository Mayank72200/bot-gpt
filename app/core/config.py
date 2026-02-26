from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BOT GPT"
    environment: str = "dev"
    debug: bool = True

    database_url: str = "sqlite:///./bot_gpt.db"

    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_chat_model: str = "mistral-small-latest"
    mistral_embedding_model: str = "mistral-embed"
    mistral_timeout_seconds: float = 20.0
    hf_token: str = Field(default="", validation_alias="HF_TOKEN")

    max_context_tokens: int = 4000
    max_history_messages: int = 10
    sliding_window_min_messages: int = 6
    rag_context_max_tokens: int = 1600
    response_token_reserve: int = 600

    vector_dim: int = 1024
    vector_index_path: str = "./data/index.faiss"

    rag_top_k: int = 6
    chunk_size_chars: int = 700
    chunk_overlap_chars: int = 100

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOTGPT_", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
