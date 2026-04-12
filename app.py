import streamlit as st
from openai import OpenAI

# 从 Streamlit Secrets 读取 API Key
zhipu_client = OpenAI(
    api_key=st.secrets["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

deepseek_client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# 页面配置
st.set_page_config(
    page_title="AI聊天工具 - 智谱 & DeepSeek",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# 标题和介绍
st.title("🤖 AI聊天工具")
st.markdown("""
**支持智谱AI (GLM-4) 和 DeepSeek**  
低成本 · 高性能 · 连续对话  
比 ChatGPT 更实惠的选择
""")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 设置")
    model_choice = st.radio(
        "选择模型",
        options=["智谱AI (GLM-4)", "DeepSeek"],
        index=0,
        help="智谱AI 对话自然，DeepSeek 推理能力强"
    )
    
    temperature = st.slider(
        "创意度",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
        help="越高越有创意，越低回答越稳定"
    )
    
    st.markdown("---")
    if st.button("🗑️ 清空所有聊天记录", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.success("✅ 聊天记录已清空")
        st.rerun()

    st.caption("💡 小贴士\n"
               "• 智谱AI 适合日常聊天\n"
               "• DeepSeek 适合复杂问题\n"
               "• 支持上下文记忆")

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示聊天记录
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 用户输入
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("AI 正在思考..."):
            try:
                if model_choice == "智谱AI (GLM-4)":
                    client = zhipu_client
                    model_name = "glm-4"
                    model_display = "智谱AI"
                else:
                    client = deepseek_client
                    model_name = "deepseek-chat"
                    model_display = "DeepSeek"

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
                st.error(f"调用失败: {str(e)}")
                if "Insufficient Balance" in str(e):
                    st.warning("DeepSeek 余额不足，请前往平台充值")

st.caption("Powered by 智谱AI & DeepSeek | 已部署到海外")
