from __future__ import annotations

import argparse

from services.brain_policy import get_brain_policy, resolve_policy_key
from services.model_router import choose_auto_model
from services.task_classifier import classify_task


def main() -> int:
    parser = argparse.ArgumentParser(
        description="查看 Megor Brain 对单个问题的完整路由结果。"
    )
    parser.add_argument("prompt", help="需要分析的问题")
    parser.add_argument("--image", action="store_true", help="模拟用户上传图片")
    args = parser.parse_args()

    task = classify_task(args.prompt, has_image=args.image)
    policy = get_brain_policy(task)
    decision = choose_auto_model(args.prompt, has_image=args.image)

    print("=" * 72)
    print("问题：", args.prompt)
    print("任务：", task.task_type)
    print("复杂度：", task.complexity)
    print("需要搜索：", task.need_search)
    print("需要视觉：", task.need_vision)
    print("语言：", task.language)
    print("分类原因：", task.reason)
    print("政策：", resolve_policy_key(task))
    print("政策首选：", policy.preferred_model)
    print("允许模型：", ", ".join(policy.allowed_models))
    print("最终模型：", decision.model)
    print("路由原因：", decision.reason)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
