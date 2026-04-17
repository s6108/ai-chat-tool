import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered"
)

# 背景 + 强化按钮颜色
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #FFF8E1, #FFFCF5) !important;}
    
    /* 基础版按钮 - 浅橙色 */
    .stButton button[key="base"] {
        background: linear-gradient(90deg, #FFCC33, #FFAA00) !important;
        color: #000000 !important;
        font-weight: bold;
        border-radius: 12px;
        border: none !important;
        box-shadow: 0 4px 8px rgba(255, 180, 0, 0.3) !important;
    }
    
    /* 高级版按钮 - 深橙色 */
    .stButton button[key="premium"] {
        background: linear-gradient(90deg, #FF7700, #FF5500) !important;
        color: white !important;
        font-weight: bold;
        border-radius: 12px;
        border: none !important;
        box-shadow: 0 4px 8px rgba(255, 100, 0, 0.4) !important;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# 初始化
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("🥭 Mango AI")
st.caption("Zhipu + DeepSeek + Kimi + Doubao + Qwen\n低成本 · 高性能 · 连续对话")

# 付费按钮（直接使用 st.link_button，避免透明过渡）
col1, col2 = st.columns(2)
with col1:
    st.link_button(
        "🚀 升级基础版 ($9.99/月)",
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87",
        use_container_width=True,
        key="base"
    )

with col2:
    st.link_button(
        "⭐ 升级高级版 ($14.99/月)",
        "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a",
        use_container_width=True,
        key="premium"
    )

st.divider()

# 侧边栏
with st.sidebar:
    st.markdown("### 🥭 Mango AI")
    st.caption("多模型 AI 聊天工具")
    model_options = ["DeepSeek", "智谱 GLM-4", "Kimi", "豆包-Pro", "豆包-Lite", "通义千问"]
    selected_model = st.radio("选择模型", model_options, label_visibility="collapsed")
    
    if st.button("🗑️ 清空聊天", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 聊天区域
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                if selected_model == "DeepSeek":
                    client = OpenAI(base_url="https://api.deepseek.com", api_key=st.secrets["DEEPSEEK_API_KEY"])
                    response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

                elif selected_model == "智谱 GLM-4":
                    client = OpenAI(base_url="https://open.bigmodel.cn/api/paas/v4/", api_key=st.secrets["ZHIPU_API_KEY"])
                    response = client.chat.completions.create(model="glm-4", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

                elif selected_model == "Kimi":
                    client = OpenAI(base_url="https://api.moonshot.cn/v1", api_key=st.secrets["KIMI_API_KEY"])
                    response = client.chat.completions.create(model="moonshot-v1-8k", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

                elif selected_model == "豆包-Pro":
                    client = OpenAI(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=st.secrets["DOUBAO_API_KEY"])
                    response = client.chat.completions.create(model="ep-20260415022601-jm5b7", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

                elif selected_model == "豆包-Lite":
                    client = OpenAI(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=st.secrets["DOUBAO_API_KEY"])
                    response = client.chat.completions.create(model="ep-20260415023354-lx4bm", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

                elif selected_model == "通义千问":
                    client = OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", api_key=st.secrets["QWEN_API_KEY"])
                    response = client.chat.completions.create(model="qwen-plus", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

                else:
                    response = "模型调用失败，请检查配置。"

            except Exception as e:
                response = f"调用失败: {str(e)}"

            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
