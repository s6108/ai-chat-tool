from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskInfo:
    task_type: str
    need_search: bool
    need_vision: bool
    complexity: str
    language: str
    reason: str


NEWS_KEYWORDS = (
    "新闻", "时事", "国际局势", "国际新闻", "突发", "最新消息",
    "政治", "选举", "议会", "外交",
    "战争", "冲突", "军事", "制裁", "地缘政治", "社会事件",
    "白宫", "国会", "联合国", "欧盟", "北约",
    "news", "breaking news", "current affairs", "politics",
    "prime minister", "election", "parliament", "diplomacy",
    "war", "conflict", "military", "sanction", "geopolitics","新聞",
    "國際新聞",
    "戰爭",
    "衝突",
    )

REALTIME_INDICATORS = (
    "今天",
    "今日",
    "刚刚",
    "最新",
    "近期",
    "最近",
    "目前",
    "现在",
    "当前",
    "实时",
    "當前",
    "現在",

    "today",
    "latest",
    "breaking",
    "breaking news",
    "just now",
    "right now",
    "currently",
    "current",
    "recent",
    "recently",
    "update",
    "updates",
    "latest update",
    "latest news",
    "news today",
    "what happened",
    "what's happening",
    "live",
    "live update",
    "real time",
    "realtime",
    "as of now",
)

NEWS_ACTION_KEYWORDS = (
    "news",
    "report",
    "reported",
    "announced",
    "statement",
    "speech",
    "meeting",
    "decision",
    "policy",
    "development",
    "situation",
    "crisis",
)

UTILITY_REALTIME_KEYWORDS = (
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

GENERAL_REALTIME_KEYWORDS = (
    "最新", "今天", "今日", "明天", "明日", "昨天", "昨日", "前天",
    "本周", "上周", "这周", "本月", "上月", "今年", "去年",
    "现在", "当前", "实时", "近期", "刚刚", "现任", "政策",
    "发布", "上市", "更新", "版本", "目前",
    "latest", "today", "tomorrow", "current", "live", "recent",
    "released", "updated", "version",
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
    "代码审查", "安全审计", "性能瓶颈", "并发", "异步", "生产环境","大型",
    "大型项目","项目重构","系统架构","微服务架构","架构设计","整体架构","代码重构",
    "跨模块","跨文件","生产系统",
    "complex", "architecture", "code review", "security audit",
    "concurrency", "production", "refactor the whole",
)

MATH_KEYWORDS = (
    # 简体中文
    "数学", "方程", "概率", "函数", "微积分", "积分", "导数",
    "矩阵", "几何", "代数", "数列", "统计", "证明", "计算",
    "计算过程", "物理题", "解题",

    # 繁体中文
    "數學", "方程式", "機率", "函數", "微積分", "積分", "導數",
    "矩陣", "幾何", "代數", "數列", "統計", "證明", "計算",
    "計算過程", "物理題", "解題",

    # English
    "math", "equation", "probability", "calculus", "integral",
    "derivative", "matrix", "geometry", "algebra", "statistics",
    "prove",
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
    "contract", "transcript","pdf","PDF","文档","全文","整份","完整文件",
    "报告","合同","论文",
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
) -> TaskInfo:
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

    if _contains_any(lowered, UTILITY_REALTIME_KEYWORDS):
        return TaskInfo(
            task_type="utility_realtime",
            need_search=True,
            need_vision=False,
            complexity="low",
            language=language,
            reason="天气、股票、汇率或其他实时数据",
        )
    print("DEBUG TEXT:", repr(lowered))

    print(
        "DEBUG NEWS HIT:",
        [
            k for k in NEWS_KEYWORDS
            if k in lowered
        ]
    )

    print(
        "DEBUG REALTIME HIT:",
        [
            k for k in GENERAL_REALTIME_KEYWORDS
            if k in lowered
        ]
    )
    if _contains_any(lowered, NEWS_KEYWORDS):
        return TaskInfo(
            task_type="news",
            need_search=True,
            need_vision=False,
            complexity="medium",
            language=language,
            reason="新闻、政治或国际时事",
        )

    if (
        _contains_any(lowered, GENERAL_REALTIME_KEYWORDS)
        and not _contains_any(lowered, NEWS_KEYWORDS)
    ):
        return TaskInfo(
            task_type="general_realtime",
            need_search=True,
            need_vision=False,
            complexity="low",
            language=language,
            reason="包含明确的当前时间或最新信息要求",
        )

    if re.search(r"\b(20\d{2}|19\d{2})\b", lowered) and _contains_any(
        lowered,
        ("发生", "发布", "价格", "数据", "新闻", "政策", "选举", "上市"),
    ):
        return TaskInfo(
            task_type="general_realtime",
            need_search=True,
            need_vision=False,
            complexity="low",
            language=language,
            reason="要求核实特定年份的动态事实",
        )

    if _looks_like_math(lowered):
            return TaskInfo(
                task_type="math",
                need_search=False,
                need_vision=False,
                complexity="medium",
                language=language,
                reason="数学、计算或逻辑题",
            )

    if _contains_any(lowered, CODE_KEYWORDS):
        complex_code = (
            length > 800
            or _contains_any(lowered, COMPLEX_CODE_KEYWORDS)
        )
        return TaskInfo(
            task_type="coding",
            need_search=False,
            need_vision=False,
            complexity="high" if complex_code else "medium",
            language=language,
            reason="复杂代码或系统任务" if complex_code else "普通编程或调试",
        )

    

    if length > 2200 or _contains_any(lowered, LONG_CONTEXT_KEYWORDS):
        return TaskInfo(
            task_type="long_context",
            need_search=False,
            need_vision=False,
            complexity="high",
            language=language,
            reason="超长文本或完整文档处理",
        )

    if _contains_any(lowered, CREATIVE_LONG_WRITING_KEYWORDS):
        return TaskInfo(
            task_type="creative_writing",
            need_search=False,
            need_vision=False,
            complexity="high",
            language=language,
            reason="长篇创意、营销或商业写作",
        )

    if _contains_any(lowered, WRITING_KEYWORDS):
        return TaskInfo(
            task_type="writing",
            need_search=False,
            need_vision=False,
            complexity="medium",
            language=language,
            reason="写作、总结、改写或润色",
        )

    if _contains_any(lowered, REASONING_KEYWORDS):
        return TaskInfo(
            task_type="reasoning",
            need_search=False,
            need_vision=False,
            complexity="medium",
            language=language,
            reason="分析、比较、规划或决策",
        )

    if length <= 220 or _contains_any(lowered, FAST_TASK_KEYWORDS):
        return TaskInfo(
            task_type="fast",
            need_search=False,
            need_vision=False,
            complexity="low",
            language=language,
            reason="简短轻量任务",
        )

    return TaskInfo(
        task_type="general",
        need_search=False,
        need_vision=False,
        complexity="medium",
        language=language,
        reason="普通常识或综合问答",
    )
