import os
import streamlit as st
import requests
import json
from PIL import Image

# ================= 页面基础配置 =================
st.set_page_config(page_title="初中物理辅导Agent", layout="wide")
st.title("初中物理辅导 Agent")
st.caption("支持文字、语音、拍照及图片上传的多模态交互")

# ================= 后端接口配置 =================
backend_base = os.getenv("BACKEND_URL", "http://backend:8001")
backend_base = backend_base.rstrip("/")
FASTAPI_URL = f"{backend_base}/ask/"

# ================= 会话状态初始化 =================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ================= 输入区 =================
st.subheader("文字提问")

with st.form("question_form", clear_on_submit=True):
    user_text = st.text_area(
        "", 
        placeholder="向辅导Agent提问...", 
        height=150,
        label_visibility="collapsed" 
    )
    
    submit_button = st.form_submit_button("发送给辅导Agent", type="primary")

# ================= 多模态输入收纳区 (类似千问的+号) =================
with st.expander("📎 更多输入方式 (语音/拍照/上传)"):
    st.markdown("**⚠️ 以下功能正在开发中，敬请期待！**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🎙️ 语音输入**")
        # disabled=True 让按钮变灰，不可点击
        st.audio_input("点击录制", disabled=True)
        st.caption("语音转文字功能开发中...")
        
    with col2:
        st.markdown("**📸 拍照识别**")
        st.button("📷 打开摄像头", disabled=True)
        st.caption("拍照解题功能开发中...")
        
    with col3:
        st.markdown("**🖼️ 上传图片**")
        st.file_uploader("选择文件", type=["png", "jpg"], disabled=True)
        st.caption("图片上传功能开发中...")

# ================= 健康检查 =================
try:
    health_url = f"{backend_base}/health/"
    health_resp = requests.get(health_url, timeout=5)
    if health_resp.status_code == 200 and health_resp.json().get("status") == "ready":
        st.success("AI 辅导系统已就绪，可以开始提问啦！")
        backend_is_ready = True
    else:
        st.warning("AI 辅导系统正在加载模型中，请稍后...")
        backend_is_ready = False
except Exception:
    st.error("无法连接到后端服务，请检查后端是否启动。")
    backend_is_ready = False

st.divider()

# ================= 发送逻辑 =================
if submit_button:
    if not backend_is_ready:
        st.warning("系统还在加载模型哦，请状态变绿后再试！")
    elif user_text.strip():
        if len(user_text.strip()) < 4 or user_text.strip() in ["你好", "在吗", "新话题"]:
            st.warning("请提出具体的物理问题（例如：'干涉条纹的形成条件是什么？'）")
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_text})
            
            message_placeholder = st.empty()
            full_response = ""

            try:
                payload = {"question": user_text}
                response = requests.post(FASTAPI_URL, json=payload, stream=True, timeout=300)
                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            json_str = decoded_line[6:]
                            data = json.loads(json_str)
                            
                            if data.get("done"):
                                break
                            if data.get("error"):
                                full_response = f"❌ 后端处理出错: {data['error']}"
                                break
                                
                            if "content" in data:
                                full_response += data["content"]
                                message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                st.session_state.chat_history.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"请求后端失败: {e}")
    else:
        st.warning("请先输入文字提问哦！")

# ================= 历史对话展示区 =================
st.divider()
st.subheader("💬 当前会话历史")
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# import os
# import streamlit as st
# import requests
# import json
# import time
# from PIL import Image

# # 页面基础配置
# st.set_page_config(page_title="初中物理辅导Agent", layout="wide")
# st.title("初中物理辅导 Agent")
# st.caption("支持文字、语音、拍照及图片上传的多模态交互")

# # ================= 后端接口配置 =================
# backend_base = os.getenv("BACKEND_URL", "http://backend:8001")
# backend_base = backend_base.rstrip("/")     # 确保基础地址不带尾部斜杠，避免拼接出 //ask/
# FASTAPI_URL = f"{backend_base}/ask/"

# # ================= 会话状态初始化 =================
# if "text_input" not in st.session_state:
#     st.session_state.text_input = ""

# if "chat_history" not in st.session_state:
#     st.session_state.chat_history = []

# if "captured_picture" not in st.session_state:
#     st.session_state.captured_picture = None

# # ================= 输入区 =================

# st.subheader("文字提问")
# # 用 form 包裹，clear_on_submit=True 自动清空输入框
# with st.form("question_form", clear_on_submit=True):
#     user_text = st.text_area(
#         "",
#         placeholder="向辅导 Agent 提问",
#         height=150,
#         label_visibility="collapsed"
#     )
#     submit = st.form_submit_button("发送给辅导Agent", type="primary")

# # 2. 语音和图片输入区
# st.subheader("语音输入")
# # audio_value = st.audio_input("点击录制你的问题")
# # if audio_value:
# #     st.audio(audio_value)
# #     # TODO: 这里后续可以接入语音识别（ASR）模型，将音频转为文字传给Agent
# #     st.success("语音录制成功！（待接入语音转文字功能）")
# st.audio_input("点击录制你的问题", disabled=True)
# st.caption("🎙️ 语音输入功能开发中，敬请期待！")

# # 3. 拍照与上传区
# st.subheader("图片输入")
# col1, col2 = st.columns(2)

# with col1:
#     st.markdown("**拍照**")
#     # # 使用 st.dialog 将摄像头封装在弹窗中
#     # @st.dialog("📷 摄像头拍照")
#     # def open_camera():
#     #     picture = st.camera_input("请对准题目拍照")
#     #     if picture:
#     #         st.session_state.captured_picture = picture  # 存入 session_state
#     #         st.image(picture, caption="拍摄的照片")
#     #         st.success("拍照成功！你可以关闭此窗口。")
        
#     #     # 提供一个关闭按钮
#     #     if st.button("关闭摄像头"):
#     #         st.rerun()  # 触发重跑，弹窗消失，摄像头随之释放

#     # # 主界面上的触发按钮
#     # if st.button("📷 点击打开摄像头"):
#     #     open_camera()

#     # # 显示刚刚拍的照片
#     # if st.session_state.captured_picture:
#     #     st.image(st.session_state.captured_picture, caption="已拍摄的照片")
#     st.button("📷 点击打开摄像头", disabled=True)
#     st.caption("📸 拍照功能开发中，敬请期待！")
# with col2:
#     st.markdown("**上传图片**")
#     # uploaded_file = st.file_uploader("选择本地图片", type=["png", "jpg", "jpeg"])
#     # if uploaded_file:
#     #     image = Image.open(uploaded_file)
#     #     st.image(image, caption="上传的图片")
#     uploaded_file = st.file_uploader("选择本地图片", type=["png", "jpg", "jpeg"], disabled=True)
#     st.caption("🖼️ 图片上传功能开发中，敬请期待！")

# # 健康检查（适配 Nginx 路径）
# try:
#     # health_resp = requests.get(os.getenv("BACKEND_URL", "http://backend:8001").replace("/ask/", "/health/"), timeout=5)
#     backend_base = os.getenv("BACKEND_URL", "http://backend:8001")
#     health_url = f"{backend_base}/health/"
#     health_resp = requests.get(health_url, timeout=5)
#     if health_resp.status_code == 200 and health_resp.json().get("status") == "ready":
#         st.success("AI 辅导系统已就绪，可以开始提问啦！")
#         backend_is_ready = True
#     else:
#         st.warning("AI 辅导系统正在加载模型中，请稍后...")
#         backend_is_ready = False
# except Exception:
#     st.error("无法连接到后端服务，请检查后端是否启动。")
#     backend_is_ready = False

# st.divider()

# # ================= 统一发送按钮 =================
# # 用 form 的 submit 变量判断，而不是 st.button
# if submit:
#     if not backend_is_ready:
#         st.warning("系统还在加载模型哦，请状态变绿后再试！")
#     elif user_text.strip():
#         # === 严格问题校验（防AI乱回答） ===
#         if len(user_text.strip()) < 4 or user_text.strip() in ["你好", "在吗", "新话题"]:
#             st.warning("请提出具体的物理问题（例如：'干涉条纹的形成条件是什么？'）")
#         else:
#             # 1. 在界面上显示用户的问题
#             st.session_state.chat_history.append({"role": "user", "content": user_text})
            
#             # 2. 准备一个占位符，用于流式显示 AI 的回答
#             message_placeholder = st.empty()
#             full_response = ""

#             # 3. 向后端 FastAPI 发送请求
#             try:
#                 # 注意：这里不需要传 session_id，让后端自动生成即可
#                 payload = {"question": user_text}
                
#                 # stream=True 是解析 SSE 流式数据的关键
#                 response = requests.post(FASTAPI_URL, json=payload, stream=True, timeout=300)
#                 response.raise_for_status()

#                 # 4. 逐行读取后端返回的流式数据（打字机效果）
#                 for line in response.iter_lines():
#                     if line:
#                         decoded_line = line.decode('utf-8')
#                         # 后端返回的格式是 "data: {...}"
#                         if decoded_line.startswith("data: "):
#                             json_str = decoded_line[6:]  # 去掉 "data: " 前缀
#                             data = json.loads(json_str)
                            
#                             # 如果后端发送了结束标志，退出循环
#                             if data.get("done"):
#                                 break
#                             # 如果后端报错，显示错误信息
#                             if data.get("error"):
#                                 full_response = f"❌ 后端处理出错: {data['error']}"
#                                 break
                                
#                             # 拼接内容并实时渲染
#                             if "content" in data:
#                                 full_response += data["content"]
#                                 message_placeholder.markdown(full_response + "▌")  # 加个光标效果
                
#                 # 5. 流式输出结束，显示最终完整结果，并加入历史
#                 message_placeholder.markdown(full_response)
#                 st.session_state.chat_history.append({"role": "assistant", "content": full_response})

#             except Exception as e:
#                 st.error(f"请求后端失败: {e}")
        
#     # elif st.session_state.captured_picture or uploaded_file:
#     #     st.info("辅导Agent收到图片！")
#     #     st.warning("图片多模态识别功能正在开发中，敬请期待...")
#     # elif audio_value:
#     #     st.info("辅导Agent收到语音消息！")
#     #     st.warning("语音转文字功能正在开发中，敬请期待...")
#     # === 非文本输入统一拦截 ===
#     elif st.session_state.captured_picture or uploaded_file:
#         st.info("该功能正在开发中，当前仅支持文字提问哦！")
#     else:
#         st.warning("请先输入文字、录制语音或上传图片哦！")


# # ================= 历史对话展示区（可选，放在页面底部或侧边栏） =================

# st.divider()
# st.subheader("💬 当前会话历史")
# for msg in st.session_state.chat_history:
#     with st.chat_message(msg["role"]):
#         st.markdown(msg["content"])
    
