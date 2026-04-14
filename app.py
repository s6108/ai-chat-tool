import streamlit as st
from openai import OpenAI

# ==================== API Keys from st.secrets ====================
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

# ==================== 支付链接 ====================
PAYMENT_LINK_BASIC = "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/4e54840f-f7b5-4ccb-9051-f193b3a5ea87"
PAYMENT_LINK_PREMIUM = "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a"

# 页面配置
st.set_page_config(
    page_title="AI Chat Tool",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("🤖 AI Chat Tool / 多模型AI聊天工具")
st.markdown("""
**Zhipu AI + DeepSeek + Kimi + Doubao + Qwen**  
Low Cost · High Performance · Continuous Chat / 低成本 · 高性能 · 连续对话
""")

# 初始化 session_state（提前初始化，避免 AttributeError）
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False
if "daily_tokens" not in st.session_state:
    st.session_state.daily_tokens = 0

# 侧边栏
with st.sidebar:
    st.header("⚙️ Settings / 设置")
    
    model_option = st.radio(
        "Select Model / 选择模型",
        options=[
            "DeepSeek (Recommended - Cheaper & Fast) / DeepSeek（推荐 - 性价比最高）",
            "智谱 GLM-4 (Natural Chinese) / 智谱 GLM-4（中文对话自然）",
            "Kimi (Strong Long Context) / Kimi（超长上下文强）",
            "豆包-Pro (Powerful) / 豆包-Pro（能力强）",
            "豆包-Lite (Fast & Cheap) / 豆包-Lite（更快更省）",
            "通义千问 (Balanced) / 通义千问（综合均衡）"
        ],
        index=0
    )

    temperature = st.slider("Creativity / 创意度", 0.0, 1.0, 0.7, 0.1)

    st.markdown("---")
    if st.button("🗑️ Clear Chat History / 清空聊天记录", use_container_width=True):
        st.session_state.messages = []
        st.success("Chat history cleared / 已清空")

# 模型映射
model_map = {
    "DeepSeek (Recommended - Cheaper & Fast) / DeepSeek（推荐 - 性价比最高）": 
        (deepseek_client, "deepseek-chat", "DeepSeek"),
    "智谱 GLM-4 (Natural Chinese) / 智谱 GLM-4（中文对话自然）": 
        (zhipu_client, "glm-4", "智谱AI"),
    "Kimi (Strong Long Context) / Kimi（超长上下文强）": 
        (kimi_client, "kimi-k2.5", "Kimi"),
    "豆包-Pro (Powerful) / 豆包-Pro（能力强）": 
        (doubao_client, "Doubao-Seed-2.0-pro", "豆包-Pro"),
    "豆包-Lite (Fast & Cheap) / 豆包-Lite（更快更省）": 
        (doubao_client, "Doubao-Seed-2.0-lite", "豆包-Lite"),
    "通义千问 (Balanced) / 通义千问（综合均衡）": 
        (qwen_client, "qwen3.6-plus", "通义千问")
}

client, model_name, display_name = model_map[model_option]

# 付费状态和升级按钮
if st.session_state.is_premium:
    st.success("✅ You are a Premium User · Unlimited Access / 您是付费用户 · 无限使用")
else:
    st.info(f"Free User · Used ~ {st.session_state.daily_tokens//1000}k tokens today / 免费用户 · 今日已用约 {st.session_state.daily_tokens//1000}k tokens")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.link_button(
            label="Upgrade Basic ($9.99/month) / 升级基础版 ($9.99/月)",
            url=PAYMENT_LINK_BASIC,
            type="primary",
            use_container_width=True
        )
    with col2:
        st.link_button(
            label="Upgrade Premium ($14.99/month) / 升级高级版 ($14.99/月)",
            url=PAYMENT_LINK_PREMIUM,
            type="secondary",
            use_container_width=True
        )

# 聊天逻辑
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask me anything... / 输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f"{display_name} is thinking... / {display_name} 正在思考..."):
            try:
                temp = 1.0 if "Kimi" in display_name else temperature
                response = client.chat.completions.create(
                    model=model_name,
                    messages=st.session_state.messages,
                    temperature=temp,
                    max_tokens=1024
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.daily_tokens += len(prompt) * 2 + len(answer)
            except Exception as e:
                st.error(f"{display_name} 调用失败: {str(e)}")

st.caption("Powered by Chinese Multi-Models · Deployed Overseas / 由中国多模型驱动 · 已部署到海外")
