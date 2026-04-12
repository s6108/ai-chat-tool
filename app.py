import streamlit as st
from openai import OpenAI

# 更新后的支付链接（$9.99版）—— 请确认你的 Lemon Squeezy 链接是否已更新
PAYMENT_LINK = "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87"

zhipu_client = OpenAI(
    api_key=st.secrets["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

deepseek_client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI Chat Tool", page_icon="🤖", layout="centered")

st.title("🤖 AI Chat Tool")
st.markdown("**Zhipu AI + DeepSeek** · Low Cost · High Performance · Continuous Chat")

if "is_premium" not in st.session_state:
    st.session_state.is_premium = False

if "daily_tokens" not in st.session_state:
    st.session_state.daily_tokens = 0

with st.sidebar:
    st.header("⚙️ Settings")
    model_choice = st.radio("Select Model", ["智谱AI (GLM-4)", "DeepSeek"], index=0)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.7, 0.1)

    st.markdown("---")
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.success("Chat history cleared")

if st.session_state.is_premium:
    st.success("✅ You are a Premium User · Unlimited Access")
else:
    st.info(f"Free User · Used ~ {st.session_state.daily_tokens//1000}k tokens today")
    st.markdown("---")
    if st.button("🚀 Upgrade to Premium ($9.99/month)", type="primary", use_container_width=True):
        st.link_button(
            label="Pay $9.99/month - Unlock Unlimited Usage",
            url=PAYMENT_LINK,
            type="primary",
            use_container_width=True
        )

# 聊天部分保持不变
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
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
                    st.warning("Free quota is almost used up! Upgrade for unlimited access.")

            except Exception as e:
                st.error(f"Error: {str(e)}")

st.caption("Powered by Zhipu AI & DeepSeek | Deployed Overseas")
