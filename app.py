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
        /* 隐藏 Streamlit 默认的 chat_input 和 file_uploader */
        .stChatInput, .stFileUploader {
            display: none !important;
        }
        
        /* 主内容区域自动滚动 */
        .main .block-container {
            padding-bottom: 100px !important;
        }
        
        /* 自定义底部固定栏 */
        .fixed-bottom-input {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 12px 20px 25px 20px;
            z-index: 999;
            border-top: 1px solid rgba(0,0,0,0.08);
            box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
        }
        
        /* 底部输入栏内部布局 */
        .bottom-input-wrapper {
            display: flex;
            gap: 12px;
            align-items: center;
            max-width: 800px;
            margin: 0 auto;
        }
        
        /* 输入框容器 */
        .input-container {
            flex: 1;
            position: relative;
        }
        
        /* 自定义输入框 */
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
            padding-right: 50px;
        }
        
        .custom-textarea:focus {
            border-color: #ff9800;
            box-shadow: 0 0 0 3px rgba(255,152,0,0.1);
        }
        
        /* 发送按钮 */
        .send-btn {
            position: absolute;
            right: 8px;
            bottom: 6px;
            background: #ff9800;
            border: none;
            border-radius: 50%;
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            color: white;
            font-size: 16px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .send-btn:hover {
            background: #ff6b00;
            transform: scale(1.05);
        }
        
        .send-btn:active {
            transform: scale(0.95);
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
        }
        
        .plus-image-btn:active {
            transform: scale(0.95);
        }
        
        /* 图片预览区域 */
        .image-preview {
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: white;
            border-radius: 12px;
            padding: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            display: flex;
            gap: 8px;
            align-items: center;
            border: 1px solid #ff9800;
        }
        
        .image-preview img {
            max-height: 60px;
            border-radius: 8px;
        }
        
        .remove-image {
            background: #ff4444;
            color: white;
            border: none;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
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
            .send-btn {
                width: 32px;
                height: 32px;
                font-size: 14px;
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
    "DeepSeek":  {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "key": DEEPSEEK_API_KEY},
    "GLM-4V":    {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4v-plus", "key": ZHIPU_API_KEY},
    "GLM-4":     {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-plus", "key": ZHIPU_API_KEY},
    "Kimi":      {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "key": KIMI_API_KEY},
    "Doubao-Pro":{"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "ep-20260415022601-jm5b7", "key": DOUBAO_API_KEY},
    "Qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "key": DASHSCOPE_API_KEY},
}

# ====================== 自动选择模型 ======================
def auto_select_model(has_image=False, text_length=0):
    """根据图片和文本长度自动选择模型"""
    if has_image:
        return "GLM-4V"  # 有图片 → GLM-4V
    if text_length > 800:
        return "Kimi"     # 长文本 >800字 → Kimi
    return "DeepSeek"     # 默认模型

# ====================== 初始化 Session State ======================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "DeepSeek"
if "auto_mode" not in st.session_state:
    st.session_state.auto_mode = True
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
if "uploaded_image_b64" not in st.session_state:
    st.session_state.uploaded_image_b64 = None

# ====================== 侧边栏 ======================
with st.sidebar:
    st.title("🥭 Mango AI")
    
    # 模型选择模式
    st.markdown("### 模型选择模式")
    mode = st.radio("", ["🤖 自动选择", "🎮 手动选择"], 
                    index=0 if st.session_state.auto_mode else 1,
                    label_visibility="collapsed")
    st.session_state.auto_mode = (mode == "🤖 自动选择")
    
    if not st.session_state.auto_mode:
        st.markdown("### 手动选择模型")
        for name in model_options.keys():
            label = "🔴 " + name if st.session_state.selected_model == name else "⚪ " + name
            if st.button(label, key=f"btn_{name}", use_container_width=True):
                st.session_state.selected_model = name
                st.rerun()
    else:
        st.info("📌 **自动选择规则**\n\n"
                "• 🖼️ 有图片 → **GLM-4V**\n"
                "• 📝 长文本(>800字) → **Kimi**\n"
                "• ⭐ 默认 → **DeepSeek**")
    
    st.markdown("---")
    st.markdown("### 💎 升级会员")
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🚀 基础版", "#")
    with col2:
        st.link_button("🔥 高级版", "#")

# ====================== 主界面 ======================
st.title("🥭 Mango AI")
st.markdown("**智能多模型 · 支持图片**")

# 清空对话按钮
if st.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.session_state.uploaded_image = None
    st.session_state.uploaded_image_b64 = None
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

# 显示图片预览（如果有）
if st.session_state.uploaded_image:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(st.session_state.uploaded_image, caption="📎 已选择图片", use_container_width=True)
        if st.button("✖️ 移除图片", key="remove_img"):
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_b64 = None
            st.rerun()

# ====================== 底部固定输入栏（包含发送按钮和+号按钮）======================
# 隐藏的文件上传器（完全隐藏，由+号按钮触发）
uploaded_file = st.file_uploader(
    "", 
    type=["png", "jpg", "jpeg", "webp"], 
    label_visibility="collapsed",
    key="hidden_uploader"
)

# 处理图片上传
if uploaded_file and uploaded_file != st.session_state.get("last_uploaded"):
    st.session_state.uploaded_image = uploaded_file
    st.session_state.last_uploaded = uploaded_file
    st.session_state.uploaded_image_b64 = base64.b64encode(uploaded_file.getvalue()).decode()
    st.rerun()

# 使用 HTML + JavaScript 实现底部输入栏
st.markdown(f'''
<div class="fixed-bottom-input">
    <div class="bottom-input-wrapper">
        <div class="input-container">
            <textarea id="user-input" class="custom-textarea" rows="1" 
                      placeholder="输入你的问题..." style="overflow-y: hidden;"></textarea>
            <button id="send-btn" class="send-btn" title="发送">➤</button>
        </div>
        <button id="plus-btn" class="plus-image-btn" title="上传图片">+</button>
    </div>
</div>

<script>
    // 获取元素
    const textarea = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const plusBtn = document.getElementById('plus-btn');
    
    // 自动调整文本框高度
    if (textarea) {{
        textarea.addEventListener('input', function() {{
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        }});
        
        // 回车发送消息
        textarea.addEventListener('keypress', function(e) {{
            if (e.key === 'Enter' && !e.shiftKey) {{
                e.preventDefault();
                const message = this.value.trim();
                if (message) {{
                    const url = new URL(window.location.href);
                    url.searchParams.set('prompt', message);
                    window.location.href = url.toString();
                }}
            }}
        }});
    }}
    
    // 发送按钮点击事件
    if (sendBtn) {{
        sendBtn.addEventListener('click', function() {{
            const message = textarea ? textarea.value.trim() : '';
            if (message) {{
                const url = new URL(window.location.href);
                url.searchParams.set('prompt', message);
                window.location.href = url.toString();
            }}
        }});
    }}
    
    // + 号按钮触发文件上传
    if (plusBtn) {{
        plusBtn.addEventListener('click', function() {{
            // 找到隐藏的文件上传器
            const fileInput = document.querySelector('input[type="file"][data-testid="stFileUploader"]');
            if (fileInput) {{
                fileInput.click();
            }}
        }});
    }}
</script>
''', unsafe_allow_html=True)

# ====================== 处理输入 ======================
query_params = st.query_params
url_prompt = query_params.get("prompt", "")
if url_prompt:
    # 清除 URL 参数
    st.query_params.clear()
else:
    url_prompt = None

# 处理消息
if url_prompt or st.session_state.uploaded_image:
    prompt = url_prompt or ""
    has_image = st.session_state.uploaded_image is not None
    
    if prompt or has_image:
        # 计算文本长度
        text_length = len(prompt) if prompt else 0
        
        # 自动选择模型
        if st.session_state.auto_mode:
            selected = auto_select_model(has_image, text_length)
            st.session_state.selected_model = selected
        else:
            selected = st.session_state.selected_model
        
        # 构建用户消息内容
        if has_image:
            # 带图片的消息
            user_content = [
                {"type": "text", "text": prompt or "请描述这张图片"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{st.session_state.uploaded_image_b64}"}}
            ]
            
            # 显示用户消息
            with st.chat_message("user"):
                if prompt:
                    st.markdown(prompt)
                st.image(st.session_state.uploaded_image, caption="📎 上传的图片")
            
            st.session_state.messages.append({"role": "user", "content": user_content})
            
            # 清空图片
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_b64 = None
        else:
            # 纯文本消息
            with st.chat_message("user"):
                st.markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 调用 AI
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            try:
                cfg = model_options[selected]
                
                if not cfg["key"]:
                    placeholder.error(f"❌ {selected} 的 API Key 未配置")
                    full_response = f"抱歉，{selected} 模型未配置，请联系管理员。"
                else:
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
                error_msg = str(e)
                placeholder.error(f"调用失败: {error_msg[:200]}")
                full_response = f"抱歉，出错了：{error_msg[:200]}"
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        
        st.rerun()

# 显示当前模型状态
if st.session_state.auto_mode:
    st.caption(f"🤖 自动模式 | 当前模型: **{st.session_state.selected_model}**")
else:
    st.caption(f"🎮 手动模式 | 当前模型: **{st.session_state.selected_model}**（可在侧边栏切换）") 
