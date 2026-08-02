"""政策答疑子图：意图分析 → 检索 → 校验引用 → 生成回答。"""

from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from services.agent_runtime.state import AssistantState
from services.rag.retrieval import hybrid_search, build_context, build_citations


@dataclass
class PolicyAgent:
    db: AsyncSession
    llm: ChatOpenAI | None = None

    def __post_init__(self):
        if self.llm is None:
            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=0.1,
            )

    async def retrieve(self, state: AssistantState) -> dict:
        """检索相关文档"""
        query = state["messages"][-1].content if state.get("messages") else ""
        chunks = await hybrid_search(self.db, query)
        if not chunks:
            return {"evidence": [], "warnings": ["未找到相关政策文档"]}

        return {
            "evidence": [{
                "evidence_id": c["chunk_id"],
                "content": c["content"],
                "title": c["document_title"],
                "trust_level": c["trust_level"],
                "score": c["score"],
            } for c in chunks],
            "warnings": [],
        }

    async def generate(self, state: AssistantState) -> dict:
        evidence = state.get("evidence", [])
        messages = state.get("messages", [])
        query = messages[-1].content if messages else ""

        if not evidence:
            return {
                "answer": {
                    "content": "抱歉，当前知识库中未收录该问题的相关政策文档。建议您查阅南大本科生院官网或咨询教务处获取权威解答。",
                    "citations": [],
                    "confidence": 0.0,
                },
                "confidence": 0.0,
                "warnings": state.get("warnings", []) + ["无相关证据"],
            }

        chunk_dicts = [{
            "chunk_id": e["evidence_id"], "content": e["content"],
            "document_title": e["title"], "trust_level": e["trust_level"],
            "score": e["score"], "chunk_index": 0, "metadata": {}, "valid_from": None,
        } for e in evidence]

        ctx = build_context(chunk_dicts)

        system = SystemMessage(content=f"""你是南京大学辅修政策答疑助手"福小禾"。请根据以下政策文档回答用户问题。

严格规则：
1. 只使用提供的政策文档内容回答，不得编造
2. 引用具体条款时，标注来源编号
3. 若文档未覆盖用户问题，明确说"当前知识库未收录"，并建议官方渠道
4. 回答简洁、条理清晰，适合本科生理解
5. 涉及学分、证书等关键信息必须准确

政策文档：
{ctx}""")

        response = await self.llm.ainvoke([system, HumanMessage(content=query)])
        citations = build_citations(chunk_dicts[:5])
        top_score = evidence[0]["score"]

        return {
            "answer": {
                "content": response.content,
                "citations": citations,
                "confidence": top_score,
            },
            "confidence": top_score,
            "warnings": state.get("warnings", []),
            "_evidence": evidence,
        }

    async def verify(self, state: AssistantState) -> dict:
        """校验引用覆盖：各项政策断言是否有来源支撑。"""
        answer = state.get("answer", {})
        evidence = state.get("evidence", [])
        warnings = list(state.get("warnings", []))

        content = answer.get("content", "") if isinstance(answer, dict) else str(answer)
        confidence = state.get("confidence", 0.0)

        # 无证据 → 已有拒答，不改
        if not evidence or not content.strip():
            return {"warnings": warnings}

        # 低分检索 → 标记
        if confidence < 0.3:
            warnings.append("检索相关度较低，回答可能不准确")
            confidence = max(confidence, 0.2)

        # LLM 校验引用覆盖
        evidence_texts = "\n---\n".join(
            f"[{i+1}] {e.get('content', '')[:300]}" for i, e in enumerate(evidence[:5])
        )
        check_prompt = SystemMessage(content=f"""检查以下回答中的每条政策事实是否被提供的文档所支持。

证据文档：
{evidence_texts}

回答：
{content}

判断规则：
- 若所有关键事实（学分、证书、流程等）均被至少一条证据覆盖 → covered
- 若存在无法从证据中验证的事实 → uncoverable
- 若证据不足但仍回复了部分合理推断 → partial

只回复: covered, partial, 或 uncoverable，以及一句话原因。""")

        try:
            check_resp = await self.llm.ainvoke([check_prompt])
            verdict = check_resp.content.lower()

            if "uncoverable" in verdict:
                warnings.append("部分回答内容无法从知识库验证")
                confidence = min(confidence, 0.4)
            elif "partial" in verdict:
                warnings.append("部分内容为合理推断，非直接引用")
                confidence = min(confidence, 0.6)
        except Exception:
            pass  # 校验失败不影响回答

        return {
            "confidence": confidence,
            "warnings": warnings,
        }

    def build(self) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("retrieve", self.retrieve)
        builder.add_node("generate", self.generate)
        builder.add_node("verify", self.verify)
        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", "verify")
        builder.add_edge("verify", END)
        return builder.compile()


def create_policy_agent(db: AsyncSession) -> StateGraph:
    agent = PolicyAgent(db)
    return agent.build()
