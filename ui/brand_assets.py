from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_DIR / "static"

LOGO_PATH = STATIC_DIR / "logo.png"
USER_AVATAR = str(STATIC_DIR / "avatar-user.png")


MODEL_AVATARS = {
    "DeepSeek": str(STATIC_DIR / "avatar-deepseek.png"),
    "Qwen": str(STATIC_DIR / "avatar-qwen.png"),
    "GLM-4V": str(STATIC_DIR / "avatar-glm-4v.png"),
    "GLM-4": str(STATIC_DIR / "avatar-glm-4.png"),
    "Kimi": str(STATIC_DIR / "avatar-kimi.png"),
    "Doubao-Pro": str(STATIC_DIR / "avatar-doubao-pro.png"),
    "ChatGPT": str(STATIC_DIR / "avatar-chatgpt.png"),
    "Gemini": str(STATIC_DIR / "avatar-gemini.png"),
    "Grok": str(STATIC_DIR / "avatar-grok.png"),
    "Claude": str(STATIC_DIR / "avatar-claude.png"),
    "Mango AI": str(STATIC_DIR / "avatar-mango-ai.png"),
}


def model_avatar(model_name: str) -> str:
    return MODEL_AVATARS.get(
        model_name,
        MODEL_AVATARS["Mango AI"],
    )


def render_brand_header(compact: bool = False) -> None:
    width = 92 if compact else 150

    c1, c2 = st.columns(
        [1, 4],
        vertical_alignment="center",
    )

    with c1:
        st.image(
            str(LOGO_PATH),
            width=width,
        )

    with c2:
        st.markdown("# Mango AI")


def apply_brand_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stChatMessage"]
        [data-testid="stCaptionContainer"] p {
            color: #6b7280 !important;
            font-weight: 500;
        }

        [data-testid="stChatMessageAvatarUser"],
        [data-testid="stChatMessageAvatarAssistant"] {
            border-radius: 13px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )