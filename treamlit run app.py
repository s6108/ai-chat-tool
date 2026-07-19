[1mdiff --git a/app.py b/app.py[m
[1mindex eb2316a..0d9595d 100644[m
[1m--- a/app.py[m
[1m+++ b/app.py[m
[36m@@ -242,6 +242,11 @@[m [mmodel_options = {[m
         "model": "qwen-plus",[m
         "key": DASHSCOPE_API_KEY,[m
     },[m
[32m+[m[32m    "ChatGPT": {[m[41m[m
[32m+[m[32m        "base_url": "https://api.openai.com/v1",[m[41m[m
[32m+[m[32m        "model": "gpt-5.4-mini",[m[41m[m
[32m+[m[32m        "key": OPENAI_API_KEY,[m[41m[m
[32m+[m[32m    }[m[41m[m
 }[m
 [m
 MODEL_ICONS = {[m
[36m@@ -251,6 +256,7 @@[m [mMODEL_ICONS = {[m
     "Kimi": "🔵",[m
     "Doubao-Pro": "🟢",[m
     "Qwen": "🟣",[m
[32m+[m[32m    "ChatGPT": "⚫",[m[41m [m
 }[m
 [m
 MODEL_SELECTOR_OPTIONS = [[m
[36m@@ -261,6 +267,7 @@[m [mMODEL_SELECTOR_OPTIONS = [[m
     "🔵 Kimi",[m
     "🟢 Doubao-Pro",[m
     "🟣 Qwen",[m
[32m+[m[32m    "⚫ ChatGPT",[m[41m[m
 ][m
 [m
 MODEL_LABEL_TO_NAME = {[m
[36m@@ -270,6 +277,7 @@[m [mMODEL_LABEL_TO_NAME = {[m
     "🔵 Kimi": "Kimi",[m
     "🟢 Doubao-Pro": "Doubao-Pro",[m
     "🟣 Qwen": "Qwen",[m
[32m+[m[32m    "⚫ ChatGPT": "ChatGPT",[m[41m[m
 }[m
 # ====================== Chat Database Functions ======================[m
 def handle_model_selector_change():[m
[36m@@ -1006,13 +1014,19 @@[m [mif st.session_state.processing:[m
             else:[m
                 api_messages = [m for m in st.session_state.messages if isinstance(m.get("content"), str)][m
 [m
[31m-            stream = client.chat.completions.create([m
[31m-                model=cfg["model"],[m
[31m-                messages=api_messages,[m
[31m-                stream=True,[m
[31m-                temperature=0.7,[m
[31m-                max_tokens=2000,[m
[31m-            )[m
[32m+[m[32m            request_params = {[m[41m[m
[32m+[m[32m                "model": cfg["model"],[m[41m[m
[32m+[m[32m                "messages": api_messages,[m[41m[m
[32m+[m[32m                "stream": True,[m[41m[m
[32m+[m[32m            }[m[41m[m
[32m+[m[41m[m
[32m+[m[32m            if st.session_state.selected_model == "ChatGPT":[m[41m[m
[32m+[m[32m                request_params["max_completion_tokens"] = 2000[m[41m[m
[32m+[m[32m            else:[m[41m[m
[32m+[m[32m                request_params["temperature"] = 0.7[m[41m[m
[32m+[m[32m                request_params["max_tokens"] = 2000[m[41m[m
[32m+[m[41m[m
[32m+[m[32m            stream = client.chat.completions.create(**request_params)[m[41m[m
 [m
             for chunk in stream:[m
                 if chunk.choices and chunk.choices[0].delta.content:[m
