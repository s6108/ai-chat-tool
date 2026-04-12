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

st.set_page_config(page_title="AI聊天工具", page_icon="🤖", layout="centered")

st.title("🤖 AI聊天工具")
st.markdown("**智谱AI + DeepSeek** · 低成本 · 高性能 · 连续对话")

# 付费状态（先用简单session模拟，后续可换数据库）
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False

if "daily_tokens" not in st.session_state:
    st.session_state.daily_tokens = 0

# 侧边栏
with st.sidebar:
    st.header("⚙️ 设置")
    model_choice = st.radio("选择模型", ["智谱AI (GLM-4)", "DeepSeek"], index=0)
    temperature = st.slider("创意度", 0.0, 1.0, 0.7, 0.1)

    st.markdown("---")
    if st.button("🗑️ 清空聊天记录", use_container_width=True):
        st.session_state.messages = []
        st.success("聊天记录已清空")

    st.caption("💡 当前使用情况\n免费用户每天限额 · 付费用户无限使用")

# 显示付费状态栏
if st.session_state.is_premium:
    st.success("✅ 您是付费用户 · 享受无限使用")
else:
    st.info(f"免费用户 · 今日已用 {st.session_state.daily_tokens//1000}k Token")

# 聊天逻辑（简化版 + Token 简单计数）
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
        with st.spinner("AI思考中..."):
            try:
                if model_choice == "智谱AI (GLM-4)":
                    client = zhipu_client
                    model_name = "glm-4"
                else:
                    client = deepseek_client
                    model_name = "deepseek-chat"

                response = client.chat.completions.create(
                    model=model_name,
                    messages=st.session_state.messages,
                    temperature=temperature,
                    max_tokens=1024
                )
                answer = response.choices[0].message.content
                
                # 简单 Token 计数（实际可更精确）
                st.session_state.daily_tokens += len(prompt) * 2 + len(answer)

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"调用失败: {str(e)}")

    # 免费用户达到一定额度后显示升级提示
    if not st.session_state.is_premium and st.session_state.daily_tokens > 80000:
        st.warning("免费额度即将用完！升级付费版解锁无限使用")
        if st.button("🚀 升级为付费用户（每月 $6.9）", type="primary"):
            st.info("支付页面开发中... 目前可联系我测试付费版")

st.caption("Powered by 智谱AI & DeepSeek | 已部署到海外")
