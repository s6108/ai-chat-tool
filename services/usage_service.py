from datetime import date


FREE_CHAT_LIMIT = 30
FREE_IMAGE_LIMIT = 5


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
    if plan == "premium":
        return True

    usage = get_today_usage(supabase_admin, user_id)
    return int(usage.get("chat_count", 0)) < FREE_CHAT_LIMIT


def can_use_image(supabase_admin, user_id: str, plan: str = "free") -> bool:
    if plan == "premium":
        return True

    usage = get_today_usage(supabase_admin, user_id)
    return int(usage.get("image_count", 0)) < FREE_IMAGE_LIMIT