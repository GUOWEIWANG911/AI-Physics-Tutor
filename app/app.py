import os
import streamlit as st
import requests
import json
import time
from PIL import Image

# 页面基础配置
st.set_page_config(page_title="初中物理辅导Agent", layout="wide")
st.title("初中物理辅导 Agent")
st.caption("支持文字、语音、拍照及图片上传的多模态交互")

# ================= 后端接口配置 =================
# 在 Docker 中，Streamlit 和 FastAPI 在同一个容器内，直接用 localhost 即可
# FASTAPI_URL = "http://localhost:8001/ask"
FASTAPI_URL = os.getenv("BACKEND_URL", "http://backend:8001/ask")

# ================= 会话状态初始化 =================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "captured_picture" not in st.session_state:
    st.session_state.captured_picture = None

# ================= 输入区 =================
user_text = st.text_area("文字提问", placeholder="在这里输入你的物理问题...")

# 2. 语音和图片输入区
st.subheader("语音输入")
audio_value = st.audio_input("点击录制你的问题")
if audio_value:
    st.audio(audio_value)
    # TODO: 这里后续可以接入语音识别（ASR）模型，将音频转为文字传给Agent
    st.success("语音录制成功！（待接入语音转文字功能）")

# 3. 拍照与上传区
st.subheader("图片输入")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**拍照**")

    # 使用 session_state 来记录摄像头是否开启，默认关闭
    # """
    # 问题一：为什么每次都要点 2 次才能生效？
    # 这是 Streamlit 的自顶向下自动重跑机制导致的。
    # 当你点击 Checkbox 时，Streamlit 会重新运行整个脚本。但有时候，组件的渲染状态和 Checkbox 的值没有完全同步，导致你需要再点一次来触发重跑，让界面刷新。

    # 问题二：为什么摄像头指示灯一直亮着，并没有实际关闭？
    # 这是因为 st.camera_input 这个组件的设计机制。即使你通过 if 语句把它隐藏了，它在后台可能依然保持着硬件连接，或者浏览器出于安全策略没有立刻释放摄像头权限。
    # """
    # if "camera_on" not in st.session_state:
    #     st.session_state.camera_on = False

    # # 提供一个开关按钮
    # st.session_state.camera_on = st.checkbox("开启/关闭摄像头", value=st.session_state.camera_on)

    # # 只有当开关打开时，才显示拍照组件
    # if st.session_state.camera_on:
    #     picture = st.camera_input("打开摄像头拍照")
    #     if picture:
    #         st.image(picture, caption="拍摄的照片")
    #         # 拍完照后，可以自动关闭摄像头（可选）
    #         # st.session_state.camera_on = False
    #     else:
    #         st.info("点击上方复选框以打开摄像头")

    # 使用 st.dialog 将摄像头封装在弹窗中
    @st.dialog("📷 摄像头拍照")
    def open_camera():
        picture = st.camera_input("请对准题目拍照")
        if picture:
            st.session_state.captured_picture = picture  # 存入 session_state
            st.image(picture, caption="拍摄的照片")
            st.success("拍照成功！你可以关闭此窗口。")
        
        # 提供一个关闭按钮
        if st.button("关闭摄像头"):
            st.rerun()  # 触发重跑，弹窗消失，摄像头随之释放

    # 主界面上的触发按钮
    if st.button("📷 点击打开摄像头"):
        open_camera()

    # 显示刚刚拍的照片
    if st.session_state.captured_picture:
        st.image(st.session_state.captured_picture, caption="已拍摄的照片")

with col2:
    st.markdown("**上传图片**")
    uploaded_file = st.file_uploader("选择本地图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="上传的图片")

# 每次页面刷新或交互时，先检查后端状态
try:
    health_resp = requests.get(os.getenv("BACKEND_URL", "http://backend:8001").replace("/ask", "/health"), timeout=5)
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

# ================= 统一发送按钮 =================
if st.button("发送给辅导Agent", type="primary"):
    if not backend_is_ready:
        st.warning("系统还在加载模型哦，请状态变绿后再试！")
    elif user_text:
        # 1. 在界面上显示用户的问题
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        
        # 2. 准备一个占位符，用于流式显示 AI 的回答
        message_placeholder = st.empty()
        full_response = ""

        # 3. 向后端 FastAPI 发送请求
        try:
            # 注意：这里不需要传 session_id，让后端自动生成即可
            payload = {"question": user_text}
            
            # stream=True 是解析 SSE 流式数据的关键
            response = requests.post(FASTAPI_URL, json=payload, stream=True, timeout=300)
            response.raise_for_status()

            # 4. 逐行读取后端返回的流式数据（打字机效果）
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    # 后端返回的格式是 "data: {...}"
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]  # 去掉 "data: " 前缀
                        data = json.loads(json_str)
                        
                        # 如果后端发送了结束标志，退出循环
                        if data.get("done"):
                            break
                        # 如果后端报错，显示错误信息
                        if data.get("error"):
                            full_response = f"❌ 后端处理出错: {data['error']}"
                            break
                            
                        # 拼接内容并实时渲染
                        if "content" in data:
                            full_response += data["content"]
                            message_placeholder.markdown(full_response + "▌")  # 加个光标效果
            
            # 5. 流式输出结束，显示最终完整结果，并加入历史
            message_placeholder.markdown(full_response)
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"请求后端失败: {e}")

    elif st.session_state.captured_picture or uploaded_file:
        st.info("辅导Agent收到图片！")
        st.warning("图片多模态识别功能正在开发中，敬请期待...")
    elif audio_value:
        st.info("辅导Agent收到语音消息！")
        st.warning("语音转文字功能正在开发中，敬请期待...")
    else:
        st.warning("请先输入文字、录制语音或上传图片哦！")

# ================= 历史对话展示区（可选，放在页面底部或侧边栏） =================
st.divider()
st.subheader("💬 当前会话历史")
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    
