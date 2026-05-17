import streamlit as st
import os
import base64
from openai import OpenAI

st.set_page_config(page_title="Mango AI", page_icon="🥭", layout="centered")

# 自定义 CSS 实现底部固定输入栏
st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#ff9800">
    <style>
        /* 隐藏 Streamlit 默认的底部空白 */
        .main > div {
            padding-bottom: 0 !important;
        }
        
        /* 聊天消息容器 - 留出底部空间避免被遮挡 */
        .stChatMessage {
            margin-bottom: 0 !important;
        }
        
        /* 自定义底部固定栏 */
        .fixed-bottom-input {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(to top, white 95%, transparent);
            padding: 12px 20px 25px 20px;
            z-index: 999;
            backdrop-filter: blur(10px);
            border-top: 1px solid rgba(0,0,0,0.05);
            box-shadow: 0 -4px 20px rgba(0,0,0,0.05);
        }
        
        /* 底部输入栏内部布局 */
        .bottom-input-wrapper {
            display: flex;
            gap: 12px;
            align-items: center;
            max-width: 800px;
            margin: 0 auto;
            position: relative;
        }
        
        /* 输入框容器 */
        .input-container {
            flex: 1;
            position: relative;
        }
        
        /* 自定义输入框样式 */
        .custom-textarea {
            width: 100%;
            padding: 12px 16px;
            border: 1.5px solid #e0e0e0;
            border-radius: 28px;
            font-size: 15px;
            font-family: inherit;
            resize: none;
            outline: none;
            transition: all 0.2s ease;
            background: white;
            line-height: 1.5;
        }
        
        .custom-textarea:focus {
            border-color: #ff9800;
            box-shadow: 0 0 0 3px rgba(255,152,0,0.1);
        }
        
        /* + 号图片按钮 */
        .plus-image-btn {
            background: linear-gradient(135deg, #ff9800, #ff6b00);
            border: none;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            flex-shrink: 0;
            box-shadow: 0 2px 8px rgba(255,107,0,0.3);
            color: white;
            font-size: 28px;
            font-weight: bold;
        }
        
        .plus-image-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(255,107,0,0.4);
        }
        
        .plus-image-btn:active {
            transform: scale(0.95);
        }
        
        /* 为聊天区域添加底部内边距，防止最后一条消息被遮挡 */
        .stChatMessageContainer {
            margin-bottom: 100px !important;
        }
        
        /* 主内容区域自动滚动 */
        .main .block-container {
            padding-bottom: 120px !important;
        }
        
        /* 文件上传按钮样式 (替换原来的+号功能) */
        .upload-btn-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
        }
        
        /* 隐藏 Streamlit 默认的文件上传器样式，使用自定义按钮 */
        .stFileUploader > div:first-child {
            display: none !important;
        }
        
        /* 隐藏默认的 chat_input */
        .stChatInput {
            display: none !important;
        }
        
        /* 底部遮罩层，让内容淡出效果 */
        .scroll-gradient {
            position: fixed;
            bottom: 80px;
            left: 0;
            right: 0;
            height: 40px;
            background: linear-gradient(to bottom, transparent, white);
            pointer-events: none;
            z-index: 998;
        }
        
        @media (max-width: 768px) {
            .fixed-bottom-input {
                padding: 10px 16px 20px 16px;
            }
            .plus-image-btn {
                width: 44px;
                height: 44px;
                font-size: 24px;
            }
            .custom-textarea {
                font-size: 14px;
                padding: 10px 14px;
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
if "input_text" not in st.session_state:
    st.session_state.input_text = ""

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    st.markdown("### 💎 升级会员")
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🚀 基础版 $9.99", "https://yufan-ai-chat.lemonsqueezy.com/checkout/buy/18622988-9cb4-436f-a106-e3db06f8741a?lang=en")
    with col2:
        st.link_button("🔥 高级版 $14.99", "https://jjyo-ai-chat.lemonsqueezy.com/checkout/buy/ba6ddc8c-7c6f-40e1-b886-019ebc747a0a?lang=en")

    st.markdown("### 模型选择")
    for name in model_options.keys():
        label = "🔴 " + name if st.session_state.selected_model == name else "⚪ " + name
        if st.button(label, key=f"btn_{name}", use_container_width=True):
            st.session_state.selected_model = name
            st.rerun()

# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能多模型 · 支持图片**")

# 清空对话按钮
col_clear, col_spacer = st.columns([1, 5])
with col_clear:
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.input_text = ""
        st.rerun()

# 显示聊天记录
chat_container = st.container()
with chat_container:
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

# ====================== 底部固定输入栏 ======================
# 用于存储上传的图片
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None

# 使用 HTML + JavaScript 实现自定义底部输入栏
st.markdown('''
<div class="fixed-bottom-input">
    <div class="bottom-input-wrapper">
        <div class="input-container">
            <textarea id="user-input" class="custom-textarea" rows="1" placeholder="输入你的问题..." 
                      style="overflow-y: hidden;"></textarea>
        </div>
        <button id="plus-btn" class="plus-image-btn" title="上传图片">+</button>
    </div>
</div>
<div class="scroll-gradient"></div>

<script>
    // 自动调整文本框高度
    const textarea = document.getElementById('user-input');
    if (textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }
    
    // 回车发送消息
    if (textarea) {
        textarea.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const message = this.value.trim();
                if (message) {
                    // 创建隐藏输入框传递数据给 Streamlit
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.style.display = 'none';
                    input.value = message;
                    document.body.appendChild(input);
                    
                    // 触发 Streamlit 的 rerun
                    const event = new Event('input', { bubbles: true });
                    input.dispatchEvent(event);
                    
                    // 清空文本框
                    this.value = '';
                    this.style.height = 'auto';
                    
                    // 延迟移除元素
                    setTimeout(() => input.remove(), 100);
                }
            }
        });
    }
    
    // + 号按钮点击触发文件上传
    const plusBtn = document.getElementById('plus-btn');
    if (plusBtn) {
        plusBtn.addEventListener('click', function() {
            // 创建隐藏的文件输入
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/png,image/jpg,image/jpeg';
            fileInput.onchange = function(e) {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(evt) {
                        // 将图片数据存储到 localStorage
                        localStorage.setItem('uploaded_image', evt.target.result);
                        // 触发页面刷新
                        location.reload();
                    };
                    reader.readAsDataURL(file);
                }
            };
            fileInput.click();
        });
    }
</script>
''', unsafe_allow_html=True)

# ====================== 处理输入和图片 ======================
# 检查是否有上传的图片
import re

# 从 localStorage 获取图片的简单方法（使用查询参数或 session）
# 注意：这里使用一个简单的轮询方式，实际可以用 Streamlit 组件
uploaded_image = None

# 简单处理：在每次 rerun 时检查 session_state 中的图片数据
if st.session_state.get("uploaded_image"):
    uploaded_image = st.session_state.uploaded_image

# 使用 Streamlit 的文件上传器（隐藏在自定义按钮后面）
with st.expander("", expanded=False):
    col_file = st.columns([1])
    with col_file[0]:
        uploaded_file = st.file_uploader(
            "上传图片", 
            type=["png", "jpg", "jpeg"], 
            label_visibility="collapsed",
            key="image_uploader_hidden"
        )
        if uploaded_file:
            st.session_state.uploaded_image = uploaded_file
            uploaded_image = uploaded_file

# 获取用户输入（通过查询参数或 session）
# 创建一个简单的输入框用于接收 JavaScript 传递的数据
user_input = st.text_input("", key="hidden_input", label_visibility="collapsed", placeholder="")
if user_input:
    prompt = user_input
    st.session_state.input_text = ""
else:
    prompt = ""

# 处理输入
if prompt or uploaded_image:
    text_length = len(prompt) if prompt else 0
    has_image = uploaded_image is not None
    
    # 自动选择模型
    st.session_state.selected_model = auto_select_model(has_image, text_length)
    
    # 构建用户消息
    user_content = []
    display_text = prompt or ""
    
    if uploaded_image:
        # 读取图片
        if hasattr(uploaded_image, 'getvalue'):
            b64 = base64.b64encode(uploaded_image.getvalue()).decode()
        else:
            # 如果是 base64 字符串
            b64 = uploaded_image.split(',')[1] if ',' in uploaded_image else uploaded_image
        
        user_content.append({"type": "text", "text": display_text or "请描述这张图片"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        
        # 显示图片
        with st.chat_message("user"):
            if display_text:
                st.markdown(display_text)
            if hasattr(uploaded_image, 'getvalue'):
                st.image(uploaded_image, caption="✅ 图片已上传")
            else:
                st.image(f"data:image/jpeg;base64,{b64}", caption="✅ 图片已上传")
        
        # 清除图片状态
        st.session_state.uploaded_image = None
    else:
        user_content = display_text
    
    # 添加到消息历史
    if uploaded_image:
        st.session_state.messages.append({"role": "user", "content": user_content})
    else:
        st.session_state.messages.append({"role": "user", "content": display_text})
    
    # 显示用户消息（如果没有图片且已显示）
    if not uploaded_image and prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
    
    # 调用 AI
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            cfg = model_options[st.session_state.selected_model]
            client = OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])
            
            # 准备消息历史
            api_messages = []
            for m in st.session_state.messages:
                api_messages.append({"role": m["role"], "content": m["content"]})
            
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=api_messages,
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
    
    # 强制刷新页面以清除输入
    st.rerun()

# 显示当前模型
st.caption(f"当前模型: **{st.session_state.selected_model}**（侧边栏切换）")
