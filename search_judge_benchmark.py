from __future__ import annotations

import statistics
import time

from services.search_judge import (
    judge_search_need,
)


TEST_CASES = [
    {
        "prompt": "你好",
        "need_search": False,
        "search_type": "none",
    },
    {
        "prompt": "为什么天空是蓝色的？",
        "need_search": False,
        "search_type": "none",
    },
    {
        "prompt": "加拿大总理是谁？",
        "need_search": True,
        "search_type": "current_fact",
    },
    {
        "prompt": "卡尔加里今天的天气怎么样？",
        "need_search": True,
        "search_type": "realtime_data",
    },
    {
        "prompt": "总结一下这段文章",
        "need_search": False,
        "search_type": "none",
    },
    {
        "prompt": "分析中美AI未来三年的竞争格局",
        "need_search": True,
        "search_type": "general_web",
    },
]


def main() -> None:
    durations = []
    passed = 0

    print("=" * 72)
    print("Qwen Search Judge Benchmark")
    print("=" * 72)

    for index, case in enumerate(
        TEST_CASES,
        start=1,
    ):
        prompt = case["prompt"]

        print()
        print(
            f"[{index}/{len(TEST_CASES)}] "
            f"{prompt}"
        )

        wall_start = time.perf_counter()

        try:
            decision = judge_search_need(
                prompt
            )

            wall_elapsed = (
                time.perf_counter()
                - wall_start
            )

            durations.append(
                decision.elapsed_seconds
            )

            correct = (
                decision.need_search
                == case["need_search"]
                and decision.search_type
                == case["search_type"]
            )

            if correct:
                passed += 1

            print(
                "  need_search:",
                decision.need_search,
            )
            print(
                "  search_type:",
                decision.search_type,
            )
            print(
                "  complexity:",
                decision.complexity,
            )
            print(
                "  api_elapsed:",
                f"{decision.elapsed_seconds:.3f}s",
            )
            print(
                "  wall_elapsed:",
                f"{wall_elapsed:.3f}s",
            )
            print(
                "  expected:",
                {
                    "need_search": (
                        case["need_search"]
                    ),
                    "search_type": (
                        case["search_type"]
                    ),
                },
            )
            print(
                "  result:",
                "PASS" if correct else "FAIL",
            )
            print(
                "  raw:",
                decision.raw_text,
            )

        except Exception as error:
            print(
                "  result: ERROR"
            )
            print(
                "  error:",
                repr(error),
            )

    print()
    print("=" * 72)
    print(
        f"Accuracy: "
        f"{passed}/{len(TEST_CASES)} "
        f"({passed / len(TEST_CASES) * 100:.1f}%)"
    )

    if durations:
        print(
            "Average API latency:",
            f"{statistics.mean(durations):.3f}s",
        )
        print(
            "Median API latency:",
            f"{statistics.median(durations):.3f}s",
        )
        print(
            "Fastest:",
            f"{min(durations):.3f}s",
        )
        print(
            "Slowest:",
            f"{max(durations):.3f}s",
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
