from __future__ import annotations

from collections import defaultdict

from services.model_router import choose_auto_model
from services.task_classifier import classify_task
from tests.validation_cases import VALIDATION_CASES


def main() -> int:
    total = len(VALIDATION_CASES)
    passed = 0
    category_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failures: list[str] = []

    print("=" * 88)
    print("Megor Brain Validation Suite")
    print("=" * 88)

    for index, case in enumerate(VALIDATION_CASES, start=1):
        task = classify_task(case.prompt, has_image=case.has_image)
        decision = choose_auto_model(case.prompt, has_image=case.has_image)

        ok = decision.model == case.expected_model
        category_stats[case.category][1] += 1

        if ok:
            passed += 1
            category_stats[case.category][0] += 1
            status = "PASS"
        else:
            status = "FAIL"
            failures.append(
                f"{case.prompt} | expected={case.expected_model} "
                f"| actual={decision.model} | task={task.task_type} "
                f"| complexity={task.complexity}"
            )

        print(
            f"[{status}] {index:02d}. {case.prompt}\n"
            f"       task={task.task_type}, complexity={task.complexity}, "
            f"expected={case.expected_model}, actual={decision.model}\n"
            f"       reason={decision.reason}"
        )

    print("\n" + "=" * 88)
    print("分类统计")
    print("=" * 88)

    for category in sorted(category_stats):
        category_passed, category_total = category_stats[category]
        print(f"{category:<20} {category_passed}/{category_total}")

    print("\n" + "=" * 88)
    print(f"总计：{passed}/{total} 通过")
    print("=" * 88)

    if failures:
        print("\n失败项目：")
        for item in failures:
            print(f"- {item}")
        return 1

    print("\n全部通过，可以提交和部署。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
