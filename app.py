import streamlit as st
from openai import OpenAI

# ==================== 从 Streamlit Secrets 读取 API Keys ====================
# 注意：这些 Key 不要写在代码里！请在 Streamlit Cloud 的 Secrets 中设置

zhipu_client = OpenAI(
    api_key=st.secrets["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

deepseek_client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

kimi_client = OpenAI(
    api_key=st.secrets["KIMI_API_KEY"],
    base_url="https://api.moonshot.cn/v1"
)

doubao_client = OpenAI(
    api_key=st.secrets["DOUBAO_API_KEY"],
    base_url="https://ark.cn-beijing.volces.com/api/v3"
)

qwen_client = OpenAI(
    api_key=st.secrets["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 页面配置
st.set_page_config(page_title="AI Chat Tool", page_icon="🤖", layout="centered")

st.title("🤖 多模型 AI 聊天工具")
st.markdown("**DeepSeek + 智谱 + Kimi + 豆包 + 通义千问** · 低成本 · 高性能 · 多场景适配")

# 侧边栏模型选择
with st.sidebar:
    st.header("⚙️ 模型选择")
    model_option = st.radio(
        "选择模型",
        options=[
            "DeepSeek (推荐 - 性价比最高)",
            "智谱 GLM-4 (中文对话自然)",
            "Kimi (超长上下文强)",
            "豆包 (速度快、创意好)",
            "通义千问 (综合能力均衡)"
        ],
        index=0
    )

    temperature = st.slider("创意度", 0.0, 1.0, 0.7, 0.1)

    st.markdown("---")
    if st.button("🗑️ 清空聊天记录", use_container_width=True):
        st.session_state.messages = []
        st.success("已清空")

# 模型映射
model_map = {
    "DeepSeek (推荐 - 性价比最高)": (deepseek_client, "deepseek-chat", "DeepSeek"),
    "智谱 GLM-4 (中文对话自然)": (zhipu_client, "glm-4", "智谱AI"),
    "Kimi (超长上下文强)": (kimi_client, "kimi-k2.5", "Kimi"),
    "豆包 (速度快、创意好)": (doubao_client, "doubao-1-5-pro-32k", "豆包"),
    "通义千问 (综合能力均衡)": (qwen_client, "qwen3.6-plus", "通义千问")
}

client, model_name, display_name = model_map[model_option]

# 聊天逻辑
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f"{display_name} 正在思考..."):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=st.session_state.messages,
                    temperature=temperature,
                    max_tokens=1024
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"{display_name} 调用失败: {str(e)}")

st.caption("Powered by 中国多模型 · 已部署到海外")
