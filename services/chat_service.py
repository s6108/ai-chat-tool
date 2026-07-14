from database import supabase_admin


def save_message(
    session_id,
    role,
    content,
    model_name=None,
    model_icon=None,
):
    if not session_id:
        return

    supabase_admin.table("messages").insert(
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "model_name": model_name,
            "model_icon": model_icon,
        }
    ).execute()