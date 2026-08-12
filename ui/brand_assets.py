from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_DIR / "static"

BRAND_LOGO_PATH = STATIC_DIR / "megor-icon-transparent.png"

ICON_PATH = STATIC_DIR / "megor-icon.png"
USER_AVATAR = str(STATIC_DIR / "avatar-user.png")

MODEL_AVATARS = {
    "DeepSeek": str(STATIC_DIR / "avatar-deepseek.png"),
    "Qwen": str(STATIC_DIR / "avatar-qwen.png"),
    "GLM": str(STATIC_DIR / "avatar-glm-4v.png"),
    "Kimi": str(STATIC_DIR / "avatar-kimi.png"),
    "Doubao-Pro": str(STATIC_DIR / "avatar-doubao-pro.png"),
    "ChatGPT": str(STATIC_DIR / "avatar-chatgpt.png"),
    "Gemini": str(STATIC_DIR / "avatar-gemini.png"),
    "Grok": str(STATIC_DIR / "avatar-grok.png"),
    "Claude": str(STATIC_DIR / "avatar-claude.png"),
    "Megor": str(STATIC_DIR / "avatar-megor.png"),
}


def model_avatar(model_name: str) -> str:
    """返回模型对应的 Megor M 徽章。"""
    return MODEL_AVATARS.get(
        model_name,
        MODEL_AVATARS["Megor"],
    )


def render_brand_header(width: int = 56) -> None:
    st.image(
        str(ICON_PATH),
        width=width,
    )

    st.markdown(
        """
        <div style="
            font-size:45px;
            font-weight:700;
            margin-top:-97px;
            margin-left:80px;
        ">
        Megor
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar_logo(width: int = 72) -> None:
    """
    Sidebar 顶部显示完整品牌 Logo。
    """
    st.image(
        str(BRAND_LOGO_PATH),
        width=width,
    )

def render_centered_text(text: str) -> None:
    st.markdown(
        f'<div class="megor-centered-text">{text}</div>',
        unsafe_allow_html=True,
    )


def apply_brand_css() -> None:
    st.markdown(
        """
        <style>
        .megor-centered-text {
            text-align: center;
            margin-top: 0.35rem;
            margin-bottom: 1.25rem;
            color: #31333f;
            font-size: 1rem;
        }
        div[data-testid="stSelectbox"] {
            width:180px;
        }

        

        [data-testid="stChatMessageAvatarUser"],
        [data-testid="stChatMessageAvatarAssistant"] {
            border-radius: 13px !important;
        }

        /* 模型标题恢复为清晰的正常深色，不使用浅灰色。 */
        .megor-model-title {
            color: #31333f;
            font-weight: 600;
            margin: 0 0 0.45rem 0;
            line-height: 1.25;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
