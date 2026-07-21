import os

import streamlit as st
from dotenv import load_dotenv


load_dotenv()

def get_key(name: str) -> str | None:
    """读取任意环境变量。"""
    value = os.getenv(name)

    if value is None:
        return None

    value = value.strip()
    return value or None
# ================= Supabase =================

SUPABASE_URL = get_key("SUPABASE_URL")
SUPABASE_KEY = get_key("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = get_key("SUPABASE_SERVICE_KEY")

# ================= Authentication =================

COOKIE_PASSWORD = get_key("COOKIE_PASSWORD")

# ================= AI Model API Keys =================

DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")
OPENAI_API_KEY = get_key("OPENAI_API_KEY")

# ================= Tavily =================

TAVILY_API_KEY = get_key("TAVILY_API_KEY")


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