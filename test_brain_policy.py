from services.brain_policy import get_brain_policy, resolve_policy_key
from services.model_router import choose_auto_model
from services.task_classifier import classify_task


TEST_PROMPTS = (
    "你好",
    "法国首都是哪里",
    "解一道微积分题",
    "写一个 Python 排序函数",
    "帮我重构一个大型 Python 项目",
    "请审查这个大型项目的架构和跨文件代码",
    "总结这篇长文",
    "写一份商业计划书",
    "今天有哪些重要国际新闻",
    "曙光股份上周收盘价是多少",
)


for prompt in TEST_PROMPTS:
    task = classify_task(prompt)
    policy = get_brain_policy(task)
    decision = choose_auto_model(prompt)

    print("=" * 70)
    print("问题：", prompt)
    print("任务：", task.task_type)
    print("复杂度：", task.complexity)
    print("政策：", resolve_policy_key(task))
    print("首选：", policy.preferred_model)
    print("实际：", decision.model)
    print("原因：", decision.reason)
