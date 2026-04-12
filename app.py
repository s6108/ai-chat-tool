import streamlit as st
from openai import OpenAI

# === 这里是支付链接 ===
PAYMENT_LINK = "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87"

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
st.set_page_config(page_title="AI聊天工具", page_icon="🤖", layout="centered")

st.title("🤖 AI聊天工具")
st.markdown("**智谱AI + DeepSeek** · 低成本 · 高性能 · 连续对话")

# 付费状态
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

# 付费状态显示 + 升级按钮
if st.session_state.is_premium:
    st.success("✅ 您是付费用户 · 享受无限使用")
else:
    st.info(f"免费用户 · 今日已用约 {st.session_state.daily_tokens//1000}k Token")
     st.markdown("---")
    if st.button("🚀 升级为付费用户（每月 ¥6.99）", type="primary", use_container_width=True):
        st.link_button(
            label="立即支付解锁无限使用",
            url=PAYMENT_LINK,
            type="primary",
            use_container_width=True
        )
# 聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 用户输入
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

                st.session_state.daily_tokens += len(prompt) * 2 + len(answer)

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

                if not st.session_state.is_premium and st.session_state.daily_tokens > 80000:
                    st.warning("免费额度即将用完！点击上方按钮升级付费版")

            except Exception as e:
                st.error(f"调用失败: {str(e)}")

st.caption("Powered by 智谱AI & DeepSeek | 已部署到海外")
st.caption(...) 之前，保持其他代码不变。
