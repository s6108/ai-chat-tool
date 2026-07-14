import os

import streamlit as st
from dotenv import load_dotenv


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
COOKIE_PASSWORD = os.getenv("COOKIE_PASSWORD")


def get_key(name: str) -> str | None:
    """读取任意环境变量。"""
    return os.getenv(name)


def validate_env() -> None:
    """检查应用启动所需的核心环境变量。"""
    required_variables = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
        "COOKIE_PASSWORD": COOKIE_PASSWORD,
    }

    missing_variables = [
        name
        for name, value in required_variables.items()
        if not value
    ]

    if missing_variables:
        st.error(
            "缺少以下环境变量：\n\n"
            + "\n".join(
                f"• {name}"
                for name in missing_variables
            )
            + "\n\n请检查本地 `.env` 或 Render Environment Variables。"
        )
        st.stop()