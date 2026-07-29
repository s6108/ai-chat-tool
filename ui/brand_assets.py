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
    """返回模型对应的 Mango M 徽章。"""
    return MODEL_AVATARS.get(
        model_name,
        MODEL_AVATARS["Mango AI"],
    )


def render_brand_header(width: int = 150) -> None:
    """在登录页或空白欢迎页居中显示完整 App Logo。"""
    left, center, right = st.columns([1, 1, 1])
    with center:
        st.image(str(LOGO_PATH), width=width)


def render_sidebar_logo(width: int = 72) -> None:
    """聊天阶段在侧边栏顶部显示较小的完整 App Logo。"""
    st.image(str(LOGO_PATH), width=width)


def render_centered_text(text: str) -> None:
    st.markdown(
        f'<div class="mango-centered-text">{text}</div>',
        unsafe_allow_html=True,
    )


def apply_brand_css() -> None:
    st.markdown(
        """
        <style>
        .mango-centered-text {
            text-align: center;
            margin-top: 0.35rem;
            margin-bottom: 1.25rem;
            color: #31333f;
            font-size: 1rem;
        }

        [data-testid="stChatMessageAvatarUser"],
        [data-testid="stChatMessageAvatarAssistant"] {
            border-radius: 13px !important;
        }

        /* 模型标题恢复为清晰的正常深色，不使用浅灰色。 */
        .mango-model-title {
            color: #31333f;
            font-weight: 600;
            margin: 0 0 0.45rem 0;
            line-height: 1.25;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
