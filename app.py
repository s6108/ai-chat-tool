import streamlit as st
import os
from openai import OpenAI

# ====================== 页面配置 ======================
st.set_page_config(
    page_title="芒果人工智能",
    page_icon="🥭",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ====================== 安全读取 API Key ======================
def get_key(name: str):
    # 优先使用 Render Environment Variables
    key = os.getenv(name)
    if key:
        return key
    # 兼容 Streamlit Secrets（如果以后切换平台）
    try:
        return st.secrets[name]
    except:
        return None

# ====================== API Keys ======================
ZHIPU_API_KEY = get_key("ZHIPU_API_KEY")
DEEPSEEK_API_KEY = get_key("DEEPSEEK_API_KEY")
KIMI_API_KEY = get_key("KIMI_API_KEY")
DOUBAO_API_KEY = get_key("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = get_key("DASHSCOPE_API_KEY")

# ====================== 界面 ======================
st.title("🥭 芒果人工智能")
st.caption("多模型 AI 聊天工具 · 智谱 + 深搜 + 基米 + 豆包 + 通义千问 · 低成本高性能")

col1, col2 = st.columns(2)
with col1:
    st.link_button(
        "🚀 升级基础版 ($9.99/月)",
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87",
        use_container_width=True
    )
with col2:
    st.link_button(
        "⭐ 升级高级版 ($14.99/月)",
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a",
        use_container_width=True
    )

st.divider()

# 模型选择
model_options = {
    "智谱 GLM-4": ("https://open.bigmodel.cn/api/paas/v4/", "glm-4"),
    "深搜": ("https://api.deepseek.com", "deepseek-chat"),
    "基米": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    "豆包-Pro": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415022601-jm5b7"),   # 你之前的 endpoint
    "豆包-Lite": ("https://ark.cn-beijing.volces.com/api/v3", "ep-20260415023354-lx4bm"),
    "通义千问": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus")
}

selected_model_name = st.sidebar.radio("选择模型", list(model_options.keys()), index=0)

# ====================== 聊天逻辑 ======================
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            base_url, model_name = model_options[selected_model_name]
            api_key = None

            if "智谱" in selected_model_name:
                api_key = ZHIPU_API_KEY
            elif "深搜" in selected_model_name:
                api_key = DEEPSEEK_API_KEY
            elif "基米" in selected_model_name:
                api_key = KIMI_API_KEY
            elif "豆包" in selected_model_name:
                api_key = DOUBAO_API_KEY
            elif "通义千问" in selected_model_name:
                api_key = DASHSCOPE_API_KEY

            if not api_key:
                st.error("该模型的 API Key 未设置，请检查 Environment Variables")
            else:
                try:
                    client = OpenAI(base_url=base_url, api_key=api_key)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=st.session_state.messages,
                        stream=False
                    )
                    answer = response.choices[0].message.content
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"调用失败: {str(e)}")

st.caption("由中国多模型驱动 · 海外部署")
