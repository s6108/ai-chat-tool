import streamlit as st
import os
import base64
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    <style>
        /* 隐藏 Streamlit 默认的 chat_input 避免重复 */
        .stChatInput {
            display: none !important;
        }
        
        /* 给主内容区域添加底部内边距，防止被固定栏遮挡 */
        .main .block-container {
            padding-bottom: 100px !important;
        }
        
        /* 固定底部输入栏 */
        .bottom-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 12px 20px 25px 20px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
            z-index: 100;
            border-top: 1px solid rgba(0,0,0,0.05);
        }
        
        /* 底部栏内部布局优化 */
        .bottom-bar > div {
            max-width: 800px;
            margin: 0 auto;
        }
        
        /* 调整上传按钮样式 */
        .stFileUploader button {
            background: linear-gradient(135deg, #ff9800, #ff6b00);
            border: none;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            color: white;
        }
        
        /* 移动端适配 */
        @media (max-width: 768px) {
            .bottom-bar {
                padding: 10px 16px 20px 16px;
            }
            .stFileUploader button {
                width: 44px;
                height: 44px;
                font-size: 20px;
            }
        }
    </style>
""", unsafe_allow_html=True)

# ====================== 密钥 ======================
def get_key(name: str):
    return os.getenv(name) or st.secrets.get(name)

ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 模型配置 ======================
model_options = {
    "DeepSeek":  {"base_url": "https://api.deepseek.com",          "model": "deepseek-chat",      "key": DEEPSEEK_API_KEY},
    "GLM-4V":    {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus",     "key": ZHIPU_API_KEY},
    "GLM-4":     {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-plus",      "key": ZHIPU_API_KEY},
    "Kimi":      {"base_url": "https://api.moonshot.cn/v1",        "model": "moonshot-v1-8k",     "key": KIMI_API_KEY},
    "Doubao-Pro":{"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "Qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY},
}

def auto_select_model(has_image=False, text_length=0):
    if has_image:
        return "GLM-4V"
    if text_length > 800:
        return "Kimi"
    if text_length > 300:
        return "Doubao-Pro"
    return "DeepSeek"

# ====================== 初始化 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"
if "auto_mode" not in st.session_state:
    st.session_state.auto_mode = True   # 默认开启自动选择

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    
    # 付费按钮
    st.markdown("### 💎 升级会员")
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🚀 基础版 $9.99", "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en")
    with col2:
        st.link_button("🔥 高级版 $14.99", "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en")

    # 自动/手动选择开关
    st.markdown("### 模式选择")
    if st.button("🔄 自动选择模式" if st.session_state.auto_mode else "🔧 手动选择模式", use_container_width=True):
        st.session_state.auto_mode = not st.session_state.auto_mode
        st.rerun()

    # 手动选择模型
    if not st.session_state.auto_mode:
        st.markdown("### 手动选择模型")
        for name in model_options.keys():
            label = "🔴 " + name if st.session_state.selected_model == name else "⚪ " + name
            if st.button(label, key=f"btn_{name}", use_container_width=True):
                st.session_state.selected_model = name
                st.rerun()

# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能多模型 · 支持图片**")

if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 显示聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])
        elif isinstance(msg["content"], list):
            for part in msg["content"]:
                if part.get("type") == "text":
                    st.markdown(part.get("text", ""))
                elif part.get("type") == "image_url":
                    st.image(part["image_url"]["url"])

# ====================== 固定底部输入栏 ======================
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
col_input, col_upload = st.columns([7, 1])

with col_input:
    prompt = st.chat_input("输入你的问题...")

with col_upload:
    uploaded_file = st.file_uploader("📎", type=["png","jpg","jpeg"], label_visibility="collapsed", key="img_upload")

st.markdown('</div>', unsafe_allow_html=True)

# ====================== 处理输入 ======================
if prompt or uploaded_file is not None:
    text_length = len(prompt) if prompt else 0
    has_image = uploaded_file is not None

    if st.session_state.auto_mode:
        st.session_state.selected_model = auto_select_model(has_image, text_length)

    user_content = []
    display_text = prompt or ""

    if uploaded_file:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        user_content.append({"type": "text", "text": display_text or "请描述这张图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        st.image(uploaded_file, caption="✅ 图片已上传")

    if prompt and not uploaded_file:
        user_content.append({"type": "text", "text": prompt})

    st.session_state.messages.append({"role": "user", "content": user_content or display_text})

    with st.chat_message("user"):
        st.markdown(display_text)

    # 调用AI
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            cfg = model_options[st.session_state.selected_model]
            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7,
                max_tokens=2000
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            placeholder.error(f"调用失败: {str(e)}")
            full_response = "抱歉，出错了，请重试。"

        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.caption(f"当前模型: **{st.session_state.selected_model}** | 自动模式: {'✅' if st.session_state.auto_mode else '❌'}")
