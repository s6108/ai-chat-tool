import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Mango AI",
    page_icon="🥭",
    layout="centered"
)

# 背景 + 按钮颜色
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #FFF8E1, #FFFCF5) !important;}
    
    /* 基础版按钮 - 浅橙色 */
    .stLinkButton button[key="base"] {
        background: linear-gradient(90deg, #FFCC33, #FFAA00) !important;
        color: #000000 !important;
        font-weight: bold !important;
        border-radius: 12px !important;
    }
    
    /* 高级版按钮 - 深橙色 */
    .stLinkButton button[key="premium"] {
        background: linear-gradient(90deg, #FF7700, #FF5500) !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== 全局 Client 初始化（关键优化：只创建一次） ====================
@st.cache_resource
def get_client(model_name):
    if model_name == "DeepSeek":
        return OpenAI(base_url="https://api.deepseek.com", api_key=st.secrets["DEEPSEEK_API_KEY"])
    elif model_name == "智谱 GLM-4":
        return OpenAI(base_url="https://open.bigmodel.cn/api/paas/v4/", api_key=st.secrets["ZHIPU_API_KEY"])
    elif model_name == "Kimi":
        return OpenAI(base_url="https://api.moonshot.cn/v1", api_key=st.secrets["KIMI_API_KEY"])
    elif model_name in ["豆包-Pro", "豆包-Lite"]:
        return OpenAI(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=st.secrets["DOUBAO_API_KEY"])
    elif model_name == "通义千问":
        return OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", api_key=st.secrets["QWEN_API_KEY"])
    return None

# 初始化聊天记录（限制历史长度，防止越来越慢）
if "messages" not in st.session_state:
    st.session_state.messages = []

# 限制历史消息数量（关键优化）
MAX_HISTORY = 20
if len(st.session_state.messages) > MAX_HISTORY:
    st.session_state.messages = st.session_state.messages[-MAX_HISTORY:]

# ==================== 主界面 ====================
st.title("🥭 Mango AI")
st.caption("Zhipu + DeepSeek + Kimi + Doubao + Qwen\n低成本 · 高性能 · 连续对话")

# 付费按钮
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

# ==================== 聊天区域 ====================
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
                client = get_client(selected_model)
                
                if selected_model == "豆包-Pro":
                    model_id = "ep-20260415022601-jm5b7"
                elif selected_model == "豆包-Lite":
                    model_id = "ep-20260415023354-lx4bm"
                elif selected_model == "DeepSeek":
                    model_id = "deepseek-chat"
                elif selected_model == "智谱 GLM-4":
                    model_id = "glm-4"
                elif selected_model == "Kimi":
                    model_id = "moonshot-v1-8k"
                elif selected_model == "通义千问":
                    model_id = "qwen-plus"
                else:
                    model_id = "deepseek-chat"

                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content

            except Exception as e:
                response = f"调用失败: {str(e)}"

            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

st.caption("Powered by Chinese Multi-Models · Deployed Overseas")
