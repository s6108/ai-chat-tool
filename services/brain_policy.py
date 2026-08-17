from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from services.task_classifier import TaskInfo


@dataclass(frozen=True)
class BrainPolicy:
    """
    Megor Brain 的明确任务政策。

    preferred_model:
        该任务的固定首选模型。

    fallback_models:
        首选模型不可用时的备用顺序。

    use_capability_ranking:
        True 表示允许 Model Capability Center 在候选池中评分选择；
        False 表示严格使用 preferred_model。

    allowed_models:
        开启评分时允许参与竞争的模型范围。

    prefer_chinese_models:
        在能力接近时是否优先中国模型。

    require_native_search:
        是否要求模型具备原生搜索能力。

    require_vision:
        是否要求模型具备视觉能力。
    """

    policy_name: str
    preferred_model: str
    fallback_models: tuple[str, ...]
    use_capability_ranking: bool
    allowed_models: tuple[str, ...]
    prefer_chinese_models: bool
    require_native_search: bool = False
    require_vision: bool = False
    max_tokens: int = 1200
    temperature: float = 0.4
    reason: str = ""


BRAIN_POLICIES: Final[dict[str, BrainPolicy]] = {
    # ─────────────────────────────────────────────
    # 固定政策：不允许评分覆盖
    # ─────────────────────────────────────────────

    "vision": BrainPolicy(
        policy_name="vision",
        preferred_model="GLM",
        fallback_models=("Gemini", "ChatGPT"),
        use_capability_ranking=False,
        allowed_models=("GLM", "Gemini", "ChatGPT"),
        prefer_chinese_models=True,
        require_vision=True,
        max_tokens=1200,
        temperature=0.4,
        reason="图片任务固定优先使用 GLM",
    ),

    "utility_realtime": BrainPolicy(
        policy_name="utility_realtime",
        preferred_model="DeepSeek",
        fallback_models=("Qwen", "GLM"),
        use_capability_ranking=False,
        allowed_models=("DeepSeek", "Qwen", "GLM"),
        prefer_chinese_models=True,
        max_tokens=1000,
        temperature=0.2,
        reason="天气、股票、汇率等实时数据经 Megor Search 后由 DeepSeek 整理",
    ),

    "news": BrainPolicy(
        policy_name="news",
        preferred_model="Grok",
        fallback_models=("Gemini", "Claude"),
        use_capability_ranking=False,
        allowed_models=("Grok", "Gemini", "Claude"),
        prefer_chinese_models=False,
        require_native_search=False,
        max_tokens=1400,
        temperature=0.3,
        reason="新闻、政治和国际时事固定使用国际模型",
    ),

    "general_realtime": BrainPolicy(
        policy_name="general_realtime",
        preferred_model="DeepSeek",
        fallback_models=("Qwen", "GLM"),
        use_capability_ranking=False,
        allowed_models=("DeepSeek", "Qwen", "GLM"),
        prefer_chinese_models=True,
        max_tokens=1100,
        temperature=0.3,
        reason="普通实时资料经 Megor Search 后优先由低成本中国模型整理",
    ),

    "math": BrainPolicy(
        policy_name="math",
        preferred_model="DeepSeek",
        fallback_models=("Qwen", "Claude"),
        use_capability_ranking=False,
        allowed_models=("DeepSeek", "Qwen", "Claude"),
        prefer_chinese_models=True,
        max_tokens=1500,
        temperature=0.2,
        reason="数学、计算和逻辑题固定优先使用 DeepSeek",
    ),

    "long_context": BrainPolicy(
        policy_name="long_context",
        preferred_model="Kimi",
        fallback_models=("Claude", "Gemini"),
        use_capability_ranking=False,
        allowed_models=("Kimi", "Claude", "Gemini"),
        prefer_chinese_models=True,
        max_tokens=1700,
        temperature=0.4,
        reason="超长文本和完整文档固定优先使用 Kimi",
    ),

    "creative_writing": BrainPolicy(
        policy_name="creative_writing",
        preferred_model="Doubao-Pro",
        fallback_models=("Qwen", "Claude"),
        use_capability_ranking=False,
        allowed_models=("Doubao-Pro", "Qwen", "Claude"),
        prefer_chinese_models=True,
        max_tokens=1800,
        temperature=0.75,
        reason="长篇创作、营销和商业写作固定优先使用 Doubao-Pro",
    ),

    "complex_coding": BrainPolicy(
        policy_name="complex_coding",
        preferred_model="Claude",
        fallback_models=("Grok", "DeepSeek"),
        use_capability_ranking=False,
        allowed_models=("Claude", "Grok", "DeepSeek"),
        prefer_chinese_models=False,
        max_tokens=1900,
        temperature=0.2,
        reason="大型项目、复杂架构、跨文件重构和代码审查固定使用 Claude",
    ),

    # ─────────────────────────────────────────────
    # 评分政策：只在受控候选池中评分
    # ─────────────────────────────────────────────

    "coding": BrainPolicy(
        policy_name="coding",
        preferred_model="DeepSeek",
        fallback_models=("Qwen", "Claude"),
        use_capability_ranking=True,
        allowed_models=("DeepSeek", "Qwen", "Claude"),
        prefer_chinese_models=True,
        max_tokens=1500,
        temperature=0.2,
        reason="普通编程任务在受控候选池中按能力与性价比选择",
    ),

    "writing": BrainPolicy(
        policy_name="writing",
        preferred_model="Qwen",
        fallback_models=("Doubao-Pro", "Kimi"),
        use_capability_ranking=True,
        allowed_models=("Qwen", "Doubao-Pro", "Kimi"),
        prefer_chinese_models=True,
        max_tokens=1400,
        temperature=0.65,
        reason="普通写作、总结和润色按中文能力与性价比选择",
    ),

    "reasoning": BrainPolicy(
        policy_name="reasoning",
        preferred_model="DeepSeek",
        fallback_models=("Qwen", "GLM"),
        use_capability_ranking=True,
        allowed_models=("DeepSeek", "Qwen", "GLM"),
        prefer_chinese_models=True,
        max_tokens=1400,
        temperature=0.3,
        reason="分析、比较和规划任务按推理能力与性价比选择",
    ),

    "fast": BrainPolicy(
        policy_name="fast",
        preferred_model="Qwen",
        fallback_models=("DeepSeek", "Doubao-Pro"),
        use_capability_ranking=True,
        allowed_models=("Qwen", "DeepSeek", "Doubao-Pro"),
        prefer_chinese_models=True,
        max_tokens=800,
        temperature=0.5,
        reason="简短轻量任务按速度和成本选择",
    ),

    "general": BrainPolicy(
        policy_name="general",
        preferred_model="DeepSeek",
        fallback_models=("Qwen", "GLM", "Doubao-Pro"),
        use_capability_ranking=True,
        allowed_models=("DeepSeek", "Qwen", "GLM", "Doubao-Pro"),
        prefer_chinese_models=True,
        max_tokens=1100,
        temperature=0.45,
        reason="普通常识和综合问答按质量、成本与速度综合选择",
    ),
}


def resolve_policy_key(task: TaskInfo) -> str:
    """
    把 Task Classifier 的结果映射成 Brain Policy。

    complex_coding 是政策层新增的精确任务，不要求修改 TaskInfo 数据结构。
    """
    if task.task_type == "coding" and task.complexity == "high":
        return "complex_coding"

    if task.task_type in BRAIN_POLICIES:
        return task.task_type

    return "general"


def get_brain_policy(task: TaskInfo) -> BrainPolicy:
    """读取某个任务对应的 Brain Policy。"""
    return BRAIN_POLICIES[resolve_policy_key(task)]
