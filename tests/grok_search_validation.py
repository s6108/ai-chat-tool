from services.search.search_router import (
    get_search_decision,
    get_search_provider,
)


def main():
    decision = get_search_decision(
        "Grok",
        "news",
    )

    print("search_type:", decision.search_type)
    print("provider:", decision.provider)
    print("reason:", decision.reason)

    provider = get_search_provider(
        "Grok",
        "news",
    )

    print("executor:", type(provider).__name__)

    result = provider.search(
        "今天有哪些重要国际新闻？"
    )

    print(result)


if __name__ == "__main__":
    main()