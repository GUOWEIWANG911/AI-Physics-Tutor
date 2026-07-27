import os
import streamlit as st
import requests
import json
import uuid
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

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

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
    
    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.markdown("**🎙️ 语音输入**")
        # disabled=True 让按钮变灰，不可点击
        st.audio_input("点击录制", disabled=True)
        st.caption("语音转文字功能开发中...")
        
    with col2:
        st.markdown("**📸 拍照识别**")
        st.button("📷 打开摄像头", disabled=True, use_container_width=True)     # use_container_width=True 让按钮填满列宽，和其他组件对齐
        st.caption("拍照解题功能开发中...")
        
    with col3:
        st.markdown("**🖼️ 上传图片**")
        st.file_uploader("选择文件", type=["png", "jpg"], disabled=True, label_visibility="collapsed")      # label_visibility="collapsed" 隐藏标签，只留上传框，更简洁
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
        # 只有"新对话 + 字数不足 + 是问候语"才拦截
        is_new_chat = len(st.session_state.chat_history) == 0
        is_too_short = len(user_text.strip()) < 4
        is_greeting = user_text.strip() in ["你好", "在吗", "新话题"]

        # 👇 只有三个条件同时满足才拦截，"惯性"不是问候语，所以放行
        if is_new_chat and is_too_short and is_greeting:
            st.warning("请提出具体的物理问题（例如：'惯性是什么？'）")
        else:
            # 从后端同步历史对话（带分页与降级）
            try:
                history_url = f"{backend_base}/history/{st.session_state.session_id}?limit=50"
                resp = requests.get(history_url, timeout=5)
                if resp.status_code == 200:
                    history_data = resp.json()
                    if isinstance(history_data, list) and len(history_data) > 0:
                        st.session_state.chat_history = history_data
                        st.toast(f"✅ 已同步 {len(history_data)} 条历史对话", icon="📚")
                    else:
                        st.toast("ℹ️ 暂无历史对话，将作为新话题处理", icon="📝")
                else:
                    st.toast("ℹ️ 暂无历史对话，将作为新话题处理", icon="📝")
            except Exception as e:
                st.warning(f"⚠️ 无法同步历史对话: {e}，将作为新话题处理")

            payload = {
                "question": user_text,
                "session_id": st.session_state.session_id
            }

            message_placeholder = st.empty()
            full_response = ""

            try:
                response = requests.post(FASTAPI_URL, json=payload, stream=True, timeout=300)
                response.raise_for_status()

                st.session_state.chat_history.append({"role": "user", "content": user_text.strip()})

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

    
