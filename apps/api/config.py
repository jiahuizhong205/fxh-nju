from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str = "postgresql+asyncpg://fuxiaohe:fuxiaohe_dev@localhost:5432/fuxiaohe"
    redis_url: str = "redis://localhost:6379/0"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_api_model: str = "BAAI/bge-m3"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_api_key: str = "ollama"
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k_retrieval: int = 8
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    api_key: str = ""
    mock_llm: bool = False


settings = Settings()
