from database import supabase_admin


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