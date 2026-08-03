from services.search_policy import decide_search_strategy


TEST_CASES = [

    # 普通实时数据
    (
        "DeepSeek",
        "utility_realtime",
        "mango",
    ),

    # 股票天气
    (
        "DeepSeek",
        "general_realtime",
        "mango",
    ),

    # 国际新闻
    (
        "Grok",
        "news",
        "native",
    ),

    # 科研研究
    (
        "Gemini",
        "research",
        "native",
    ),

    # Claude 长网页分析
    (
        "Claude",
        "research",
        "native",
    ),

    # 普通聊天不搜索
    (
        "Qwen",
        "general",
        "none",
    ),

]


for model, task, expected in TEST_CASES:

    result = decide_search_strategy(
        model,
        task,
    )

    actual = result.search_type

    status = (
        "PASS"
        if actual == expected
        else "FAIL"
    )

    print(
        status,
        "|",
        model,
        "|",
        task,
        "|",
        actual,
        "|",
        expected,
    )