"""统一创建外部 OpenAI 兼容聊天模型；项目不加载本地大模型。"""

from apps.api.config import settings


def create_chat_model(temperature: float):
    if settings.mock_llm:
        return None
    if not settings.llm_base_url or not settings.llm_model or not settings.llm_api_key:
        raise RuntimeError("真实 LLM 服务尚未完整配置")

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=settings.llm_base_url.rstrip("/"),
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_tokens=settings.llm_max_tokens,
        extra_body={"enable_thinking": settings.llm_enable_thinking},
    )
