from services.native_search.native_search_factory import NativeSearchFactory


def run_test():
    native_search = NativeSearchFactory.create("Gemini")

    if native_search is None:
        print("❌ Gemini native search adapter not found")
        return

    result = native_search.search(
        query="加拿大现任总理是谁？请根据最新公开信息回答。",
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