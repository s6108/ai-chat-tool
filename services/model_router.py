import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str
    max_tokens: int
    temperature: float


CODE_KEYWORDS = (
    "代码", "编程", "python", "javascript", "java", "c++", "sql", "api",
    "报错", "错误", "debug", "调试", "函数", "算法", "部署", "streamlit",
    "supabase", "render", "github", "正则", "json", "html", "css",
)

REASONING_KEYWORDS = (
    "分析", "推理", "比较", "评估", "为什么", "原因", "方案", "策略",
    "优化", "规划", "设计", "证明", "计算过程", "详细解释", "利弊",
    "analyze", "reason", "compare", "evaluate", "strategy", "design",
)

WRITING_KEYWORDS = (
    "写一篇", "撰写", "文案", "文章", "邮件", "报告", "方案书", "脚本",
    "总结", "归纳", "长文", "改写", "润色", "摘要",
)

FAST_TASK_KEYWORDS = (
    "翻译", "什么意思", "怎么读", "改成", "纠正", "简要", "简单介绍",
    "一句话", "列出", "提取", "格式化", "你好", "谢谢",
    "translate", "meaning", "rewrite", "brief", "list",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_math(text: str) -> bool:
    return bool(
        re.search(r"\d\s*[+\-*/=<>]\s*\d", text)
        or re.search(r"\b(方程|概率|函数|微积分|矩阵|几何|数学题)\b", text)
    )


def choose_auto_model(
    prompt: str,
    *,
    has_image: bool = False,
    needs_search: bool = False,
) -> RouteDecision:
    """纯本地智能调度，不增加任何额外模型请求。"""
    text = (prompt or "").strip()
    lowered = text.lower()
    length = len(text)

    if has_image:
        return RouteDecision(
            model="GLM-4V",
            reason="图片识别任务",
            max_tokens=1000,
            temperature=0.4,
        )

    # 联网问题更重视资料整合与事实表达，交给 DeepSeek。
    if needs_search:
        return RouteDecision(
            model="DeepSeek",
            reason="联网资料整合",
            max_tokens=1000,
            temperature=0.3,
        )

    # 超长输入优先使用 Kimi 的长上下文能力。
    if length > 1200:
        return RouteDecision(
            model="Kimi",
            reason="超长文本处理",
            max_tokens=1200,
            temperature=0.5,
        )

    # 编程、数学和明显复杂推理继续使用 DeepSeek，保证质量。
    if (
        _contains_any(lowered, CODE_KEYWORDS)
        or _contains_any(lowered, REASONING_KEYWORDS)
        or _looks_like_math(lowered)
    ):
        return RouteDecision(
            model="DeepSeek",
            reason="复杂推理或技术任务",
            max_tokens=1200,
            temperature=0.4,
        )

    # 中长篇写作使用豆包，避免简单任务也走重模型。
    if length > 350 or _contains_any(lowered, WRITING_KEYWORDS):
        return RouteDecision(
            model="Doubao-Pro",
            reason="写作或中长文本任务",
            max_tokens=1000,
            temperature=0.7,
        )

    # 短问答、翻译、提取、格式转换优先走 Qwen。
    if length <= 180 or _contains_any(lowered, FAST_TASK_KEYWORDS):
        return RouteDecision(
            model="Qwen",
            reason="快速轻量任务",
            max_tokens=700,
            temperature=0.5,
        )

    # 普通中等长度问题默认使用豆包。
    return RouteDecision(
        model="Doubao-Pro",
        reason="普通问答",
        max_tokens=900,
        temperature=0.6,
    )
