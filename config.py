import os
import streamlit as st


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def validate_env():
    if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_SERVICE_KEY:
        st.error("Supabase 环境变量未配置完整，请检查 Render Environment Variables。")
        st.stop()


def get_key(name: str):
    return os.getenv(name)
