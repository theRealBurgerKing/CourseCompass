"""LLM-as-judge metrics: Faithfulness and Context Recall (our own implementation, Ragas-style definitions).

Faithfulness   — are the *factual* claims in the answer supported by the context the LLM was given?
                 Opinions (advice, difficulty judgements, ...) are not scored; their share is reported.
Context Recall — can each reference key point be derived from the retrieved context alone?

The judge is configured separately from the app's models so it is not the same model that wrote the answer:
    JUDGE_API_KEY   required (never falls back to OPENAI_API_KEY)
    JUDGE_BASE_URL  default https://api.deepseek.com
    JUDGE_MODEL     default deepseek-flash   (DeepSeek-V4.1-Flash; run with thinking disabled, see _get_llm)
Results are cached on disk keyed by (metric, judge model, inputs) so unchanged cases are not re-judged.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

CACHE_DIR = Path(__file__).parent / ".cache"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


def judge_model_name() -> str:
    return os.getenv("JUDGE_MODEL") or DEFAULT_MODEL


def require_judge_key() -> None:
    if not os.getenv("JUDGE_API_KEY"):
        raise RuntimeError("JUDGE_API_KEY is not set in backend/.env (needed for --full)")


_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    """Judge LLM. The key is passed explicitly: ChatOpenAI would otherwise silently use OPENAI_API_KEY."""
    global _llm
    if _llm is None:
        require_judge_key()
        base_url = os.getenv("JUDGE_BASE_URL") or DEFAULT_BASE_URL
        # DeepSeek defaults to thinking mode, which rejects the forced tool_choice that structured output
        # needs and ignores temperature. Judging here is extraction + checking, so turn thinking off.
        extra = {"thinking": {"type": "disabled"}} if "deepseek" in base_url else None
        _llm = ChatOpenAI(
            model=judge_model_name(),
            api_key=os.environ["JUDGE_API_KEY"],
            base_url=base_url,
            temperature=0,
            max_retries=3,
            extra_body=extra,
        )
    return _llm


def _structured(schema: type[BaseModel]):
    # function_calling: DeepSeek supports tool calls / json_object but not OpenAI's json_schema response format
    return _get_llm().with_structured_output(schema, method="function_calling")


def _cached(kind: str, payload: dict, schema: type[BaseModel], system: str, human: str, use_cache: bool):
    key = hashlib.sha256(json.dumps([kind, judge_model_name(), system, payload], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    path = CACHE_DIR / f"judge_{kind}_{key}.json"
    if use_cache and path.exists():
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    result = _structured(schema).invoke([("system", system), ("human", human)])
    if result is None:
        raise ValueError("judge returned no structured output")
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(result.model_dump_json(indent=1), encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Faithfulness
# ---------------------------------------------------------------------------

class Claim(BaseModel):
    text: str = Field(description="一条原子断言，保持简短、可独立核对")
    kind: Literal["fact", "opinion"] = Field(description="fact=关于具体课程的可核对事实；opinion=建议、评价、推荐理由等")
    verdict: Literal["supported", "unsupported", "contradicted", "not_applicable"] = Field(
        description="仅对 fact 判断；opinion 一律填 not_applicable"
    )
    evidence: str = Field(default="", description="支持或反驳该断言的上下文原文片段（简短），没有则留空")


class FaithfulnessJudgement(BaseModel):
    claims: list[Claim]


_FAITH_SYSTEM = """你是严谨的评测员，负责检查一段选课顾问的回答是否忠实于给定的课程上下文。

步骤：
1. 把“待评估的回答”拆成原子断言，每条只含一个可独立核对的信息点。
2. 给每条断言标注类型 kind：
   - fact：关于具体课程的可核对陈述，例如课程代码、课程名称、开课学期、学分、学院、校区、授课方式与课时、选课限制、先修或假定知识、等价课程、课程内容范围。
   - opinion：推荐理由、学习建议、难度或工作量评价、学习路径安排、总结、寒暄等主观或建议性内容。opinion 的 verdict 一律填 not_applicable。
3. 对每条 fact 判断 verdict：
   - supported：上下文明确写出，或可由上下文直接推出。
   - contradicted：与上下文相矛盾。
   - unsupported：上下文没有提及（即使常识上可能为真，也算 unsupported）。
4. evidence 填上下文中的依据原文（简短）；没有依据则留空。

注意：
- 上下文是英文课程数据，回答是中文，请按语义对应（如 Term 2 对应“第二学期”或 T2）。
- 回答里“上下文中没有该课程/信息”这类如实承认缺失的话，不是断言，不要拆出来。
- “UNSW / 新南威尔士大学”是系统已知的背景（课程库本身就是 UNSW 的），不要因为上下文没写 UNSW 就判 unsupported。
- 只依据“课程上下文”判断，不要使用你自己的知识。"""


def judge_faithfulness(context: str, question: str, answer: str, use_cache: bool = True) -> dict:
    """Score = supported / all factual claims. Opinions are excluded from the score and reported as a share."""
    human = f"【课程上下文】\n{context}\n\n【用户问题】\n{question}\n\n【待评估的回答】\n{answer}"
    res: FaithfulnessJudgement = _cached(
        "faith", {"c": context, "q": question, "a": answer}, FaithfulnessJudgement, _FAITH_SYSTEM, human, use_cache
    )
    facts = [c for c in res.claims if c.kind == "fact" and c.verdict != "not_applicable"]
    supported = [c for c in facts if c.verdict == "supported"]
    return {
        "faithfulness": len(supported) / len(facts) if facts else None,
        "opinion_rate": (sum(c.kind == "opinion" for c in res.claims) / len(res.claims)) if res.claims else None,
        "n_facts": len(facts),
        "n_opinions": sum(c.kind == "opinion" for c in res.claims),
        "bad_claims": [c.model_dump() for c in facts if c.verdict != "supported"],
    }


# ---------------------------------------------------------------------------
# Context Recall
# ---------------------------------------------------------------------------

class PointVerdict(BaseModel):
    index: int = Field(description="要点编号，从 0 开始，与输入一致")
    supported: bool = Field(description="仅凭课程上下文能否推出该要点")
    evidence: str = Field(default="", description="上下文中的依据原文（简短），没有则留空")


class ContextRecallJudgement(BaseModel):
    points: list[PointVerdict]


_RECALL_SYSTEM = """你是严谨的评测员。给定“课程上下文”和一组“参考要点”，判断每个要点能否仅凭课程上下文推出。
- supported=true：上下文明确写出，或可直接推出该要点的全部内容。
- supported=false：上下文缺少该信息，或只覆盖了要点的一部分。
- 上下文是英文课程数据，要点是中文，请按语义对应。
- 不要使用你自己的知识补全；上下文里没有就是 false。
- 必须为输入的每个要点各返回一条，index 与输入编号一致。"""


def judge_context_recall(context: str, key_points: list[str], use_cache: bool = True) -> dict:
    """Score = key points derivable from the retrieved context / all key points."""
    if not key_points:
        return {"context_recall": None, "points": []}
    listing = "\n".join(f"{i}. {p}" for i, p in enumerate(key_points))
    human = f"【课程上下文】\n{context}\n\n【参考要点】\n{listing}"
    res: ContextRecallJudgement = _cached(
        "ctxrec", {"c": context, "p": key_points}, ContextRecallJudgement, _RECALL_SYSTEM, human, use_cache
    )
    verdicts = {v.index: v for v in res.points}
    points = []
    for i, p in enumerate(key_points):
        v = verdicts.get(i)  # a point the judge skipped is conservatively counted as not supported
        points.append({"point": p, "supported": bool(v and v.supported), "evidence": v.evidence if v else "(judge skipped)"})
    return {"context_recall": sum(p["supported"] for p in points) / len(points), "points": points}
