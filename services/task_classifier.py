from __future__ import annotations

import re
from dataclasses import dataclass

from services.freshness_service import judge_freshness


@dataclass(frozen=True)
class TaskInfo:
    task_type: str
    need_search: bool
    need_vision: bool
    complexity: str
    language: str
    reason: str
    search_type: str = "none"


CODE_KEYWORDS = (
    "代码", "编程", "程序", "python", "javascript", "typescript", "java",
    "c++", "c#", "golang", "rust", "sql", "api", "sdk", "报错", "错误",
    "debug", "调试", "函数", "算法", "部署", "streamlit", "supabase",
    "render", "github", "正则", "json", "html", "css", "数据库", "架构",
    "重构", "代码审查", "性能优化", "单元测试", "接口",
)

COMPLEX_CODE_KEYWORDS = (
    "完整项目", "大型项目", "系统设计", "复杂架构", "跨文件", "重构整个",
    "代码审查", "安全审计", "性能瓶颈", "并发", "异步", "生产环境",
    "complex", "architecture", "code review", "security audit",
    "concurrency", "production", "refactor the whole",
)

MATH_KEYWORDS = (
    "数学", "方程", "概率", "函数", "微积分", "积分", "导数", "矩阵",
    "几何", "代数", "数列", "统计", "证明", "计算过程", "物理题",
    "math", "equation", "probability", "calculus", "matrix", "geometry",
    "algebra", "statistics", "prove",
)

REASONING_KEYWORDS = (
    "分析", "推理", "比较", "评估", "为什么", "原因", "方案", "策略",
    "优化", "规划", "设计", "利弊", "决策", "逻辑", "论证",
    "analyze", "reason", "compare", "evaluate", "strategy", "design",
    "trade-off", "decision",
)

WRITING_KEYWORDS = (
    "写一篇", "撰写", "文案", "文章", "邮件", "报告", "方案书", "脚本",
    "总结", "归纳", "改写", "润色", "摘要", "提纲", "说明书", "宣传文案",
    "rewrite", "polish", "summarize", "article", "email", "report", "outline",
)

CREATIVE_LONG_WRITING_KEYWORDS = (
    "长篇", "故事", "小说", "剧本", "广告创意", "品牌故事", "营销方案",
    "演讲稿", "商业计划书", "白皮书", "creative writing", "novel",
    "story", "screenplay", "business plan", "white paper",
)

LONG_CONTEXT_KEYWORDS = (
    "全文", "整篇", "完整文档", "逐段", "长文", "长文本", "合同", "论文",
    "会议记录", "大量内容", "full document", "long document", "paper",
    "contract", "transcript",
)

FAST_TASK_KEYWORDS = (
    "翻译", "什么意思", "怎么读", "改成", "纠正", "简要", "简单介绍",
    "一句话", "列出", "提取", "格式化", "你好", "谢谢", "改写一句",
    "translate", "meaning", "rewrite", "brief", "list", "extract", "format",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def _looks_like_math(text: str) -> bool:
    return bool(
        re.search(r"\d\s*[+\-*/=<>^]\s*\d", text)
        or re.search(r"\b\d+(?:\.\d+)?%\b", text)
        or _contains_any(text, MATH_KEYWORDS)
    )


def classify_task(
    prompt: str,
    *,
    has_image: bool = False,
    skip_ai_freshness: bool = False,
) -> TaskInfo:
    """
    Classify task type and complexity.

    Search-decision design:
    - For the five Chinese-model paths, Qwen is the only web-search judge.
      There are no local realtime/news keyword rules.
    - Qwen returns both need_search and search_type; those values are reused
      by downstream native-search or Tavily fallback logic.
    - When skip_ai_freshness=True, Qwen is skipped completely. This is used
      by ChatGPT, Claude, Gemini, and Grok, where each provider decides
      independently whether to use its own native web-search capability.
    - Local rules remain only for non-search task classification such as
      coding, math, long context, writing, reasoning, and lightweight tasks.
    """
    text = (prompt or "").strip()
    lowered = text.lower()
    length = len(text)
    language = _detect_language(text)

    if has_image:
        return TaskInfo(
            task_type="vision",
            need_search=False,
            need_vision=True,
            complexity="medium",
            language=language,
            reason="用户上传了图片",
        )

    # ==================================================
    # Search decision
    # ==================================================
    if skip_ai_freshness:
        need_search = False
        search_type = "none"
        freshness_reason = (
            "AI freshness skipped; unified Responses decides web search"
        )
        print(
            "AI FRESHNESS SKIPPED:",
            {
                "query": text,
                "reason": freshness_reason,
            },
        )
    else:
        freshness = judge_freshness(text)
        need_search = bool(freshness.need_search)
        search_type = (
            freshness.search_type
            if need_search
            else "none"
        )
        freshness_reason = freshness.reason

        print(
            "AI FRESHNESS:",
            need_search,
            freshness.confidence,
            freshness.reason,
        )

    # ==================================================
    # Task/model routing
    # Search-sensitive routing comes only from Qwen search_type.
    # Remaining local rules classify non-search task characteristics only.
    # ==================================================

    # Qwen is the ONLY web-search judge for the five Chinese-model paths.
    # Local keywords no longer decide whether something is news/realtime/current.
    # We derive the routing subtype directly from Qwen's search_type.
    if need_search:
        if search_type == "realtime_data":
            return TaskInfo(
                task_type="utility_realtime",
                need_search=True,
                need_vision=False,
                complexity="low",
                language=language,
                reason=f"Qwen 判定为实时数据；{freshness_reason}",
                search_type=search_type,
            )

        if search_type == "recent_event":
            return TaskInfo(
                task_type="news",
                need_search=True,
                need_vision=False,
                complexity="medium",
                language=language,
                reason=f"Qwen 判定为近期事件；{freshness_reason}",
                search_type=search_type,
            )

        if search_type == "current_fact":
            return TaskInfo(
                task_type="general_realtime",
                need_search=True,
                need_vision=False,
                complexity="low",
                language=language,
                reason=f"Qwen 判定为当前事实；{freshness_reason}",
                search_type=search_type,
            )

    if _contains_any(lowered, CODE_KEYWORDS):
        complex_code = (
            length > 1600
            or _contains_any(lowered, COMPLEX_CODE_KEYWORDS)
        )
        return TaskInfo(
            task_type="coding",
            need_search=need_search,
            need_vision=False,
            complexity="high" if complex_code else "medium",
            language=language,
            reason="复杂代码或系统任务" if complex_code else "普通编程或调试",
            search_type=search_type,
        )

    if _looks_like_math(lowered):
        return TaskInfo(
            task_type="math",
            need_search=need_search,
            need_vision=False,
            complexity="medium",
            language=language,
            reason="数学、计算或逻辑题",
            search_type=search_type,
        )

    if length > 2200 or _contains_any(lowered, LONG_CONTEXT_KEYWORDS):
        return TaskInfo(
            task_type="long_context",
            need_search=need_search,
            need_vision=False,
            complexity="high",
            language=language,
            reason="超长文本或完整文档处理",
            search_type=search_type,
        )

    if _contains_any(lowered, CREATIVE_LONG_WRITING_KEYWORDS):
        return TaskInfo(
            task_type="creative_writing",
            need_search=need_search,
            need_vision=False,
            complexity="high",
            language=language,
            reason="长篇创意、营销或商业写作",
            search_type=search_type,
        )

    if _contains_any(lowered, WRITING_KEYWORDS):
        return TaskInfo(
            task_type="writing",
            need_search=need_search,
            need_vision=False,
            complexity="medium",
            language=language,
            reason="写作、总结、改写或润色",
            search_type=search_type,
        )

    if _contains_any(lowered, REASONING_KEYWORDS):
        return TaskInfo(
            task_type="reasoning",
            need_search=need_search,
            need_vision=False,
            complexity="medium",
            language=language,
            reason="分析、比较、规划或决策",
            search_type=search_type,
        )

    if length <= 220 or _contains_any(lowered, FAST_TASK_KEYWORDS):
        return TaskInfo(
            task_type="fast",
            need_search=need_search,
            need_vision=False,
            complexity="low",
            language=language,
            reason="简短轻量任务",
            search_type=search_type,
        )

    return TaskInfo(
        task_type="general",
        need_search=need_search,
        need_vision=False,
        complexity="medium",
        language=language,
        reason="普通常识或综合问答",
        search_type=search_type,
    )

