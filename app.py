import streamlit as st
import os
import base64
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# 自定义CSS - 完全隐藏所有不需要的默认组件
st.markdown("""
    <style>
        /* 隐藏默认的 chat input 和 file uploader 的默认显示 */
        .stChatInput, .stFileUploader > div:first-child {
            display: none !important;
        }
        
        /* 隐藏stTextInput的默认标签 */
        .stTextInput label {
            display: none !important;
        }
        
        /* 给主内容区域添加底部内边距 */
        .main .block-container {
            padding-bottom: 100px !important;
        }
        
        /* 固定底部栏 - 简洁版本 */
        .fixed-bottom-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 12px 20px 20px 20px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.08);
            z-index: 1000;
            border-top: 1px solid #eee;
        }
        
        /* 底部栏内部容器 */
        .bottom-bar-container {
            max-width: 800px;
            margin: 0 auto;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        /* 输入框容器 - 占据剩余宽度 */
        .input-wrapper {
            flex: 1;
        }
        
        /* 输入框样式 */
        .input-wrapper input {
            width: 100%;
            padding: 12px 16px;
            border: 1.5px solid #e0e0e0;
            border-radius: 28px;
            font-size: 15px;
            outline: none;
            transition: all 0.2s;
        }
        
        .input-wrapper input:focus {
            border-color: #ff9800;
            box-shadow: 0 0 0 2px rgba(255,152,0,0.1);
        }
        
        /* 按钮通用样式 */
        .btn-send, .btn-image {
            border: none;
            border-radius: 28px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        /* 发送按钮 */
        .btn-send {
            background: linear-gradient(135deg, #ff9800, #ff6b00);
            color: white;
            min-width: 70px;
        }
        
        .btn-send:hover {
            background: linear-gradient(135deg, #ff6b00, #e65c00);
            transform: translateY(-1px);
        }
        
        /* 图片按钮 */
        .btn-image {
            background: #f5f5f5;
            color: #ff9800;
            font-size: 20px;
            padding: 8px 16px;
            min-width: 60px;
        }
        
        .btn-image:hover {
            background: #ff9800;
            color: white;
        }
        
        @media (max-width: 768px) {
            .fixed-bottom-bar {
                padding: 10px 16px 16px 16px;
            }
            .btn-send, .btn-image {
                padding: 8px 12px;
                min-width: 55px;
            }
            .btn-image {
                font-size: 18px;
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
    st.session_state.auto_mode = True
if "pending_message" not in st.session_state:
    st.session_state.pending_message = None
if "pending_image" not in st.session_state:
    st.session_state.pending_image = None

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    
    st.markdown("### 💎 升级会员")
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🚀 基础版 $9.99", "#")
    with col2:
        st.link_button("🔥 高级版 $14.99", "#")

    st.markdown("### 模式选择")
    if st.button("🔄 自动选择模式" if st.session_state.auto_mode else "🔧 手动选择模式", use_container_width=True):
        st.session_state.auto_mode = not st.session_state.auto_mode
        st.rerun()

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

# ====================== 隐藏的文件上传器 ======================
uploaded_file = st.file_uploader(
    "", 
    type=["png", "jpg", "jpeg"], 
    label_visibility="collapsed",
    key="img_uploader"
)

# 处理图片上传
if uploaded_file:
    st.session_state.pending_image = uploaded_file
    st.rerun()

# ====================== 底部固定栏 (HTML + 原生input) ======================
# 使用HTML原生元素来避免Streamlit组件的冲突
import streamlit.components.v1 as components

components.html("""
    <div class="fixed-bottom-bar">
        <div class="bottom-bar-container">
            <div class="input-wrapper">
                <input type="text" id="message-input" placeholder="输入你的问题..." autocomplete="off">
            </div>
            <button class="btn-send" id="send-btn">发送</button>
            <button class="btn-image" id="image-btn">📷</button>
        </div>
    </div>
    
    <script>
        const inputEl = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const imageBtn = document.getElementById('image-btn');
        
        // 发送消息
        function sendMessage() {
            const message = inputEl.value.trim();
            if (message) {
                const url = new URL(window.location.href);
                url.searchParams.set('msg', message);
                window.location.href = url.toString();
            }
        }
        
        sendBtn.addEventListener('click', sendMessage);
        
        inputEl.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // 触发图片上传
        imageBtn.addEventListener('click', function() {
            const fileInput = document.querySelector('input[type="file"]');
            if (fileInput) {
                fileInput.click();
            }
        });
    </script>
""", height=80)

# ====================== 处理消息 ======================
import time

# 获取URL参数中的消息
query_params = st.query_params
msg = query_params.get("msg", "")

if msg:
    # 清除URL参数
    st.query_params.clear()
    
    prompt = msg
    has_image = st.session_state.pending_image is not None
    
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
        if has_image:
            st.image(st.session_state.pending_image, caption="✅ 图片已上传")
    
    # 添加到消息历史
    if has_image:
        b64 = base64.b64encode(st.session_state.pending_image.getvalue()).decode()
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]
        st.session_state.messages.append({"role": "user", "content": user_content})
        st.session_state.pending_image = None
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 自动选择模型
    if st.session_state.auto_mode:
        st.session_state.selected_model = auto_select_model(has_image, len(prompt))
    
    # 获取AI回复
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
    
    st.rerun()

# 显示当前模型
st.caption(f"当前模型: **{st.session_state.selected_model}** | 自动模式: {'✅' if st.session_state.auto_mode else '❌'}")
