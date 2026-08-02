import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str
    max_tokens: int
    temperature: float


# 新闻、政治、国际时事：自动模式不使用中国模型。
NEWS_CURRENT_AFFAIRS_KEYWORDS = (
    "新闻", "时事", "国际局势", "国际新闻", "突发", "最新消息",
    "政治", "政府", "总统", "首相", "选举", "议会", "外交",
    "战争", "冲突", "军事", "制裁", "地缘政治", "社会事件",
    "白宫", "国会", "联合国", "欧盟", "北约",
    "news", "breaking news", "current affairs", "politics", "government",
    "president", "prime minister", "election", "parliament", "diplomacy",
    "war", "conflict", "military", "sanction", "geopolitics",
)

# 天气、股票、汇率等普通实时信息：统一搜索后交给低成本中国模型。
UTILITY_SEARCH_KEYWORDS = (
    "天气", "气温", "温度", "降雨", "下雨", "下雪", "湿度", "风速",
    "空气质量", "台风", "天气预报",
    "股价", "股票价格", "股票", "行情", "指数", "市值",
    "收盘价", "开盘价", "最高价", "最低价", "涨停价", "跌停价", "涨跌幅",
    "成交价", "成交量", "市盈率", "分红", "财报", "基金净值",
    "汇率", "币价", "价格", "油价", "金价",
    "比分", "赛程", "排名", "航班", "火车", "时刻表",
    "weather", "temperature", "forecast", "rain", "snow", "humidity",
    "stock", "stock price", "market price", "exchange rate", "price",
    "score", "schedule", "flight", "timetable",
)

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
    "complex", "architecture", "code review", "security audit", "concurrency",
    "production", "refactor the whole",
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
    "演讲稿", "商业计划书", "白皮书", "creative writing", "novel", "story",
    "screenplay", "business plan", "white paper",
)

FAST_TASK_KEYWORDS = (
    "翻译", "什么意思", "怎么读", "改成", "纠正", "简要", "简单介绍",
    "一句话", "列出", "提取", "格式化", "你好", "谢谢", "改写一句",
    "translate", "meaning", "rewrite", "brief", "list", "extract", "format",
)

LONG_CONTEXT_KEYWORDS = (
    "全文", "整篇", "完整文档", "逐段", "长文", "长文本", "合同", "论文",
    "会议记录", "大量内容", "full document", "long document", "paper",
    "contract", "transcript",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_math(text: str) -> bool:
    return bool(
        re.search(r"\d\s*[+\-*/=<>^]\s*\d", text)
        or re.search(r"\b\d+(?:\.\d+)?%\b", text)
        or _contains_any(text, MATH_KEYWORDS)
    )


def _is_news_or_current_affairs(text: str) -> bool:
    return _contains_any(text, NEWS_CURRENT_AFFAIRS_KEYWORDS)


def _is_utility_search(text: str) -> bool:
    return _contains_any(text, UTILITY_SEARCH_KEYWORDS)


def choose_auto_model(
    prompt: str,
    *,
    has_image: bool = False,
    needs_search: bool = False,
) -> RouteDecision:
    """
    Mango Brain V1：在不明显影响结果质量的前提下，优先使用中国模型。

    路由原则：
    - 图片：GLM-4V
    - 国际新闻、政治、突发时事：Grok
    - 天气、股票、汇率等普通实时查询：DeepSeek
    - 普通代码、数学、推理：DeepSeek
    - 复杂大型代码任务：Claude
    - 超长文本：Kimi
    - 中文写作与轻任务：Qwen
    - 长篇创意写作：Doubao-Pro
    - 普通常识问答：DeepSeek
    """
    text = (prompt or "").strip()
    lowered = text.lower()
    length = len(text)

    if has_image:
        return RouteDecision(
            model="GLM-4V",
            reason="图片识别任务，优先使用中国视觉模型",
            max_tokens=1200,
            temperature=0.4,
        )

    # 联网任务先区分“国际新闻时事”和“普通实时查询”。
    if needs_search:
        if _is_news_or_current_affairs(lowered):
            return RouteDecision(
                model="Grok",
                reason="国际新闻、政治或突发时事，使用国际模型",
                max_tokens=1400,
                temperature=0.3,
            )

        if _is_utility_search(lowered):
            return RouteDecision(
                model="DeepSeek",
                reason="天气、股票、汇率等低成本实时查询",
                max_tokens=1000,
                temperature=0.2,
            )

        return RouteDecision(
            model="DeepSeek",
            reason="普通联网资料整合，优先使用低成本中国模型",
            max_tokens=1100,
            temperature=0.3,
        )

    # 超长上下文优先于一般任务分类。
    if length > 2200 or _contains_any(lowered, LONG_CONTEXT_KEYWORDS):
        return RouteDecision(
            model="Kimi",
            reason="超长文本或完整文档处理",
            max_tokens=1600,
            temperature=0.4,
        )

    # 复杂大型代码任务才使用 Claude；普通代码继续使用 DeepSeek。
    if _contains_any(lowered, CODE_KEYWORDS):
        if length > 1600 or _contains_any(lowered, COMPLEX_CODE_KEYWORDS):
            return RouteDecision(
                model="Claude",
                reason="复杂代码、系统设计或大型重构任务",
                max_tokens=1800,
                temperature=0.2,
            )

        return RouteDecision(
            model="DeepSeek",
            reason="普通编程或调试任务，优先使用中国模型",
            max_tokens=1400,
            temperature=0.2,
        )

    if _looks_like_math(lowered):
        return RouteDecision(
            model="DeepSeek",
            reason="数学、计算或逻辑推理任务",
            max_tokens=1400,
            temperature=0.2,
        )

    if _contains_any(lowered, REASONING_KEYWORDS):
        return RouteDecision(
            model="DeepSeek",
            reason="分析、推理或决策任务",
            max_tokens=1300,
            temperature=0.3,
        )

    # 长篇创意写作交给豆包；普通中文写作优先 Qwen。
    if _contains_any(lowered, CREATIVE_LONG_WRITING_KEYWORDS) or (
        length > 900 and _contains_any(lowered, WRITING_KEYWORDS)
    ):
        return RouteDecision(
            model="Doubao-Pro",
            reason="长篇创意或营销写作",
            max_tokens=1700,
            temperature=0.75,
        )

    if _contains_any(lowered, WRITING_KEYWORDS):
        return RouteDecision(
            model="Qwen",
            reason="中文写作、总结或润色任务",
            max_tokens=1300,
            temperature=0.65,
        )

    if length <= 220 or _contains_any(lowered, FAST_TASK_KEYWORDS):
        return RouteDecision(
            model="Qwen",
            reason="快速轻量任务",
            max_tokens=800,
            temperature=0.5,
        )

    # 普通常识与中等长度问答优先 DeepSeek，保证质量同时控制成本。
    return RouteDecision(
        model="DeepSeek",
        reason="普通常识或综合问答",
        max_tokens=1100,
        temperature=0.45,
    )
