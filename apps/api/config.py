from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str = "postgresql+asyncpg://fuxiaohe:fuxiaohe_dev@localhost:5432/fuxiaohe"
    redis_url: str = "redis://localhost:6379/0"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_api_key: str = "ollama"
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k_retrieval: int = 8


settings = Settings()
