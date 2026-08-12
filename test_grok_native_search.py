from services.native_search.native_search_factory import NativeSearchFactory


def run_test():
    native_search = NativeSearchFactory.create("Grok")

    if native_search is None:
        print("❌ Grok native search adapter not found")
        return

    result = native_search.search(
        query="请使用 X Search 搜索 X 平台上的真实帖子，不要只搜索普通网页。查找最近关于加拿大总理 Mark Carney 的公众讨论，并总结支持和批评他的主要观点。",
        messages=[],
        max_results=5,
    )

    print("\n===== TEST RESULT =====")
    print("success:", result.success)
    print("should_fallback:", result.should_fallback)
    print("error:", result.error)

    print("\n===== ANSWER =====")
    print(result.answer)

    print("\n===== SOURCES =====")
    for index, item in enumerate(result.results, start=1):
        print(
            f"{index}. "
            f"title={item.title!r} "
            f"url={item.url!r} "
            f"source={item.source!r}"
        )


if __name__ == "__main__":
    run_test()