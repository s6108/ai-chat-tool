from datetime import date


FREE_DAILY_CHAT_LIMIT = 8
FREE_DAILY_IMAGE_LIMIT = 3

PREMIUM_DAILY_CHAT_LIMIT = 100
PREMIUM_DAILY_IMAGE_LIMIT = 25

# backward compatibility
FREE_CHAT_LIMIT = FREE_DAILY_CHAT_LIMIT
FREE_IMAGE_LIMIT = FREE_DAILY_IMAGE_LIMIT

PREMIUM_CHAT_LIMIT = PREMIUM_DAILY_CHAT_LIMIT
PREMIUM_IMAGE_LIMIT = PREMIUM_DAILY_IMAGE_LIMIT


def get_today_usage(supabase_admin, user_id: str) -> dict:
    today = date.today().isoformat()

    result = (
        supabase_admin.table("user_usage")
        .select("*")
        .eq("user_id", user_id)
        .eq("usage_date", today)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    new_usage = {
        "user_id": user_id,
        "usage_date": today,
        "chat_count": 0,
        "image_count": 0,
    }

    supabase_admin.table("user_usage").insert(new_usage).execute()
    return new_usage


def increase_chat_usage(supabase_admin, user_id: str) -> int:
    usage = get_today_usage(supabase_admin, user_id)
    new_count = int(usage.get("chat_count", 0)) + 1

    (
        supabase_admin.table("user_usage")
        .update({"chat_count": new_count})
        .eq("user_id", user_id)
        .eq("usage_date", usage["usage_date"])
        .execute()
    )

    return new_count


def increase_image_usage(supabase_admin, user_id: str) -> int:
    usage = get_today_usage(supabase_admin, user_id)
    new_count = int(usage.get("image_count", 0)) + 1

    (
        supabase_admin.table("user_usage")
        .update({"image_count": new_count})
        .eq("user_id", user_id)
        .eq("usage_date", usage["usage_date"])
        .execute()
    )

    return new_count


def can_use_chat(supabase_admin, user_id: str, plan: str = "free") -> bool:
    usage = get_today_usage(supabase_admin, user_id)

    if plan == "premium":
        return (
            int(usage.get("chat_count", 0))
            < PREMIUM_DAILY_CHAT_LIMIT
        )

    return (
        int(usage.get("chat_count", 0))
        < FREE_DAILY_CHAT_LIMIT
    )


def can_use_image(supabase_admin, user_id: str, plan: str = "free") -> bool:
    usage = get_today_usage(supabase_admin, user_id)

    if plan == "premium":
        return (
            int(usage.get("image_count", 0))
            < PREMIUM_DAILY_IMAGE_LIMIT
        )

    return (
        int(usage.get("image_count", 0))
        < FREE_DAILY_IMAGE_LIMIT
    )