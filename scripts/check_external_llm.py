"""在不写入用户数据的前提下验证外部 OpenAI 兼容 LLM 与 embedding 配置。"""

from services.agent_runtime.llm import create_chat_model
from apps.api.config import settings
from services.rag.retrieval import embed_text
import httpx


def _configured(value: str, name: str) -> None:
    if not value:
        raise RuntimeError(f"缺少配置：{name}")


def main() -> None:
    if settings.mock_llm:
        raise RuntimeError("请先设置 MOCK_LLM=false，再执行真实服务连通性检查")

    for value, name in (
        (settings.llm_base_url, "LLM_BASE_URL"),
        (settings.llm_api_key, "LLM_API_KEY"),
        (settings.llm_model, "LLM_MODEL"),
        (settings.embedding_base_url, "EMBEDDING_BASE_URL"),
        (settings.embedding_api_key, "EMBEDDING_API_KEY"),
        (settings.embedding_api_model, "EMBEDDING_API_MODEL"),
    ):
        _configured(value, name)

    try:
        vector = embed_text("福小禾 embedding 连通性检查")
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"embedding 服务请求失败（HTTP {exc.response.status_code}）；请检查密钥、模型权限和 dimensions 配置"
        ) from None
    except httpx.RequestError:
        raise RuntimeError("embedding 服务网络连接失败；请检查地址、DNS、防火墙和 TLS 配置") from None
    if len(vector) != settings.embedding_dimension:
        raise RuntimeError("embedding 返回维度与数据库配置不一致")
    print(f"PASS embedding：{len(vector)} 维")

    model = create_chat_model(temperature=0)
    try:
        response = model.invoke("仅回复 OK")
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code:
            raise RuntimeError(
                f"聊天服务请求失败（HTTP {status_code}）；请检查模型名、密钥和模型权限"
            ) from None
        raise RuntimeError("聊天服务调用失败；请检查地址、模型兼容性和网络配置") from None
    content = str(getattr(response, "content", "")).strip()
    if not content:
        raise RuntimeError("LLM 未返回文本内容")
    print(f"PASS chat：模型 {settings.llm_model} 已返回内容")
    print("外部 LLM 预检通过；下一步可执行 reembed_documents.py。")


if __name__ == "__main__":
    main()
