from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str = "postgresql+asyncpg://fuxiaohe:fuxiaohe_dev@localhost:5432/fuxiaohe"
    redis_url: str = "redis://localhost:6379/0"
    # 兼容旧 .env；运行时不再加载该本地模型字段。
    embedding_model: str = ""
    embedding_api_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_api_timeout_seconds: float = 15.0
    # 0 表示不向 provider 传递 OpenAI 的 dimensions 参数；当前数据库固定存储 1024 维。
    embedding_api_dimensions: int = 0
    embedding_dimension: int = 1024
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 2
    # 为 Qwen3.8 等混合思考模型预留推理与最终答复额度；端到端仍受 75 秒限制。
    llm_max_tokens: int = 4096
    llm_enable_thinking: bool = True
    # 包含检索与生成的端到端上限；必须小于 nginx 的 120 秒读超时。
    agent_response_timeout_seconds: float = 75.0
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k_retrieval: int = 8
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    api_key: str = ""
    # 本地 / Docker 默认使用 mock，真实模型必须通过环境变量显式开启；不加载本地模型。
    mock_llm: bool = True
    # 验证码供应商可选；留空时仅创建挑战，不访问外部网络。
    verification_provider_url: str = ""
    verification_provider_api_key: str = ""
    verification_provider_timeout_seconds: float = 5.0
    verification_provider_webhook_secret: str = ""
    # 外部通知 provider 可选；留空时 worker 只保留 queued，不伪造送达。
    notification_provider_url: str = ""
    notification_provider_api_key: str = ""
    notification_provider_timeout_seconds: float = 5.0
    notification_worker_interval_seconds: int = 60
    # 反馈附件的安全扫描与对象存储均可选；留空时使用本地签名校验和数据库存储。
    feedback_scan_url: str = ""
    feedback_scan_api_key: str = ""
    feedback_scan_timeout_seconds: float = 10.0
    feedback_storage_url: str = ""
    feedback_storage_api_key: str = ""
    feedback_storage_timeout_seconds: float = 10.0
    # 云端同步 provider 可选；留空时仅使用本地同步接口。
    sync_provider_url: str = ""
    sync_provider_api_key: str = ""
    sync_provider_timeout_seconds: float = 10.0
    sync_worker_interval_seconds: int = 300


settings = Settings()
