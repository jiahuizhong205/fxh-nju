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
    # 本地 / Docker 默认使用 mock，真实模型必须通过环境变量显式开启。
    mock_llm: bool = True
    # 验证码供应商可选；留空时仅创建挑战，不访问外部网络。
    verification_provider_url: str = ""
    verification_provider_api_key: str = ""
    verification_provider_timeout_seconds: float = 5.0
    # 外部通知 provider 可选；留空时 worker 只保留 queued，不伪造送达。
    notification_provider_url: str = ""
    notification_provider_api_key: str = ""
    notification_provider_timeout_seconds: float = 5.0
    notification_worker_interval_seconds: int = 60


settings = Settings()
