import json

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
    messages = []

    for row in rows:
        content = row.get("content", "")

        if isinstance(content, str):
            stripped_content = content.strip()

            if stripped_content.startswith("["):
                try:
                    parsed_content = json.loads(stripped_content)

                    if isinstance(parsed_content, list):
                        content = parsed_content
                except (json.JSONDecodeError, TypeError):
                    pass

        messages.append(
            {
                "role": row.get("role", "user"),
                "content": content,
                "model_name": row.get("model_name"),
                "model_icon": row.get("model_icon"),
            }
        )

    return messages


def load_sessions(user_id: str):
    result = (
        supabase_admin.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )
    return result.data or []

def create_new_chat(user_id: str):
    result = (
        supabase_admin.table("chat_sessions")
        .insert({"user_id": user_id, "title": "新对话"})
        .execute()
    )
    if not result.data:
        raise RuntimeError("创建新对话失败")
    return result.data[0]["id"]


def delete_chat(session_id: str):
    if not session_id:
        return
    supabase_admin.table("messages").delete().eq("session_id", session_id).execute()
    supabase_admin.table("chat_sessions").delete().eq("id", session_id).execute()


def clear_chat_messages(session_id: str):
    if not session_id:
        return
    supabase_admin.table("messages").delete().eq("session_id", session_id).execute()


def update_chat_title_if_needed(session_id: str, prompt: str):
    if not session_id or not prompt:
        return

    result = (
        supabase_admin.table("chat_sessions")
        .select("title")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return

    old_title = result.data[0].get("title") or "新对话"
    if old_title == "新对话":
        new_title = prompt.strip().replace("\n", " ")[:22]
        if new_title:
            (
                supabase_admin.table("chat_sessions")
                .update({"title": new_title})
                .eq("id", session_id)
                .execute()
            )


    return result.data or []