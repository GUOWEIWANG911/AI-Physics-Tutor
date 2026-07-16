#!/bin/bash
# 后台启动 FastAPI 后端
uvicorn api_server:app --host 0.0.0.0 --port 8001 &

# 前台启动 Streamlit 前端
streamlit run app.py --server.port 8501 --server.address 0.0.0.0