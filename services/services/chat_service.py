from database import supabase_admin


def load_messages(session_id: str):
    result = (
        supabase_admin.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )

    rows = list(reversed(result.data or []))

    return [
        {
            "role": row.get("role", "user"),
            "content": row.get("content", ""),
        }
        for row in rows
    ]


def save_message(session_id: str, role: str, content: str):
    if not session_id:
        return

    supabase_admin.table("messages").insert(
        {
            "session_id": session_id,
            "role": role,
            "content": content,
        }
    ).execute()


def clear_chat_messages(session_id: str):
    if not session_id:
        return

    supabase_admin.table("messages").delete().eq(
        "session_id",
        session_id,
    ).execute()


def delete_chat_messages(session_id: str):
    if not session_id:
        return

    supabase_admin.table("messages").delete().eq(
        "session_id",
        session_id,
    ).execute()
