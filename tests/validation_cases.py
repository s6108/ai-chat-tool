from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationCase:
    category: str
    prompt: str
    expected_model: str
    has_image: bool = False


VALIDATION_CASES: tuple[ValidationCase, ...] = (
    ValidationCase("general", "你好", "Qwen"),
    ValidationCase("general", "法国首都是哪里？", "Qwen"),
    ValidationCase("general", "牛顿是谁？", "Qwen"),
    ValidationCase("general", "简单介绍一下太阳系", "Qwen"),

    ValidationCase("math", "解一道微积分题", "DeepSeek"),
    ValidationCase("math", "解一道微積分題", "DeepSeek"),
    ValidationCase("math", "求函数 y=x^2 的导数", "DeepSeek"),
    ValidationCase("math", "证明勾股定理", "DeepSeek"),
    ValidationCase("math", "计算 128×37", "DeepSeek"),

    ValidationCase("coding", "写一个 Python 排序函数", "DeepSeek"),
    ValidationCase("coding", "解释这段 Python 代码", "DeepSeek"),
    ValidationCase("coding", "帮我修复一个普通 JavaScript 报错", "DeepSeek"),

    ValidationCase("complex_coding", "帮我重构一个大型 Python 项目", "Claude"),
    ValidationCase("complex_coding", "设计一个大型微服务架构", "Claude"),
    ValidationCase("complex_coding", "审查这个跨文件项目的整体架构", "Claude"),
    ValidationCase("complex_coding", "对生产环境代码做安全审计", "Claude"),

    ValidationCase("utility_realtime", "武汉明天天气如何？", "DeepSeek"),
    ValidationCase("utility_realtime", "曙光股份上周收盘价是多少？", "DeepSeek"),
    ValidationCase("utility_realtime", "美元兑人民币汇率是多少？", "DeepSeek"),
    ValidationCase("utility_realtime", "苹果昨天收盘价是多少？", "DeepSeek"),

    ValidationCase("news", "今天有哪些重要国际新闻？", "Grok"),
    ValidationCase("news", "美国总统最新政策是什么？", "Grok"),
    ValidationCase("news", "最近有哪些重大国际冲突？", "Grok"),
    ValidationCase("news", "欧洲议会最新动态", "Grok"),

    ValidationCase("long_context", "总结这篇长文", "Kimi"),
    ValidationCase("long_context", "阅读整个 PDF 并总结", "Kimi"),
    ValidationCase("long_context", "请逐段分析这份完整合同", "Kimi"),

    ValidationCase("writing", "润色这段中文", "Qwen"),
    ValidationCase("writing", "帮我总结下面这段内容", "Qwen"),
    ValidationCase("writing", "写一封简洁的商务邮件", "Qwen"),

    ValidationCase("creative_writing", "写一份商业计划书", "Doubao-Pro"),
    ValidationCase("creative_writing", "写一个品牌营销方案", "Doubao-Pro"),
    ValidationCase("creative_writing", "写一篇长篇品牌故事", "Doubao-Pro"),

    ValidationCase("vision", "评价一下这张图片", "GLM", has_image=True),
    ValidationCase("vision", "识别图中的内容", "GLMV", has_image=True),
)
