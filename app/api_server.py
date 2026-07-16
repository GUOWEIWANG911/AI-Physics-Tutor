import os
import re
import json
import uuid
import uvicorn
import asyncio
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from langchain_core.messages import HumanMessage, AIMessage
import torch
from sentence_transformers import CrossEncoder

from redis_smart_cache import SmartCache
from config import TEXTBOOK_FILES, RERANKER_MODEL_PATH
from fastapi.middleware.cors import CORSMiddleware

# 导入核心逻辑
from main import (
    get_embedding, get_llm, build_knowledge_base, 
    LearningTracker,
    memory_agent, retrieval_agent, tutor_agent, get_dynamic_strategies
)

# 初始化 Redis 客户端（用于存储会话历史）
session_cache = SmartCache()

# 1. 创建一个专门处理 CPU 密集型任务的线程池（防止阻塞主协程）
cpu_pool = ThreadPoolExecutor(max_workers=4)

# 2. 记录系统是否真正就绪
is_system_ready = False

# 3. 定义应用的生命周期（启动时加载模型，关闭时清理）
@asynccontextmanager
async def lifespan(app: FastAPI):
    global embeddings, llm, vectorstore, reranker_model
    print("正在启动 AI 辅导系统...")

    # 将耗时的初始化丢给线程池执行
    loop = asyncio.get_running_loop()

    # 加载 Embedding 和 LLM
    print("正在加载 Embedding 和 LLM ...")
    embeddings = await loop.run_in_executor(cpu_pool, get_embedding)
    llm = await loop.run_in_executor(cpu_pool, get_llm)

    # 加载知识库
    print("正在加载知识库...")
    vectorstore = await loop.run_in_executor(
        cpu_pool, build_knowledge_base, TEXTBOOK_FILES, embeddings)

    # 加载重排模型（Reranker），自动检测并使用 GPU
    print("正在加载重排模型（Reranker）...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Reranker 正在使用设备：{device}")

    # 将 CrossEncoder 的初始化包装成一个普通函数，避免 run_in_executor 传参报错
    def load_reranker():
        return CrossEncoder(RERANKER_MODEL_PATH, device=device)
    
    reranker_model = await loop.run_in_executor(cpu_pool, load_reranker)

    # [关键优化]：模型预热（Warm-up）
    # 用一段假数据让模型提前完成底层初始化，消除首次请求的延迟
    print("正在预热 Reranker 模型...")
    dummy_pairs = [["预热测试", "这是一段用于预热的假文本"]]
    await loop.run_in_executor(cpu_pool, reranker_model.predict, dummy_pairs)
    print("Reranker 预热完成！")

    print("所有模型加载完毕！系统已就绪。")
    global is_system_ready
    is_system_ready = True # 记录系统已就绪
    yield  # 服务在这里保持运行，处理各种请求
    is_system_ready = False
    
    print("正在关闭 AI 辅导系统...")
    cpu_pool.shutdown(wait=True)


# 4. 初始化 FastAPI 应用
app = FastAPI(title="AI 物理辅导系统 API", version="1.0",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发阶段用 * 即可，生产环境建议改为具体域名）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. 定义请求的数据模型（规范前端传参）
class QuestionRequest(BaseModel):
    question: str # 学生的问题
    session_id: str = None # 可选，如果不传，后端自动生成

# 6. 定义一个测试接口
@app.get("/")
async def root():
    return {"message": "AI 物理辅导系统已成功启动！"}

# 健康检查接口
@app.get("/health")
async def health_check():
    if is_system_ready:
        return {"status": "ready"}
    else:
        return {"status": "loading"}

# 7. 定义辅导问答接口
@app.post("/ask")
async def ask_tutor(request: QuestionRequest):
    # 处理 session ID（隔离不同学生的对话）
    session_id = request.session_id or str(uuid.uuid4())
    redis_key = f"session:{session_id}" # 在 Redis 中加上前缀，防止和其他缓存冲突

    # 从 Redis 读取历史会话
    history_raw = session_cache.get(redis_key)
    if history_raw:
        # 如果 Redis 里有，反序列化回 LangChain 的 Message 对象
        chat_history = [
            HumanMessage(content=msg["content"]) if msg["type"] == "human" else 
        AIMessage(content=msg["content"])
            for msg in json.loads(history_raw)
        ]
    else:
        chat_history = []
        
    # 初始化当前轮次的状态（State）
    current_state = {
        "user_question": request.question,
        "history": chat_history,
        "student_summary": "",
        "retrieved_context": "",
        "dynamic_strategies": ""
    }

    loop = asyncio.get_running_loop()

    try:
        # [阶段一：同步等待阶段]
        print(f"[Stream] 开始执行前置 Agent 流程...")
         # 2. 异步执行 Memory Agent
        current_state = await loop.run_in_executor(cpu_pool, memory_agent, current_state, llm)

        # 3. 异步执行 Retrieval Agent
        current_state = await loop.run_in_executor(cpu_pool, retrieval_agent, current_state, vectorstore, session_cache, reranker_model)

        # 4. 获取动态策略并注入 State
        dynamic_strategies = await loop.run_in_executor(cpu_pool, get_dynamic_strategies)
        current_state["dynamic_strategies"] = dynamic_strategies

        # 5. 异步执行 Tutor Agent
        current_state = await loop.run_in_executor(cpu_pool, tutor_agent, current_state, llm)

        # [关键]：从 State 中获取组装好的 Message 列表
        # 假设 tutor_agent 把最终的 prompt 列表放在了 current_state["messages"] 中
        final_messages = current_state.get("messages", [])  

        # [阶段二：流式生成阶段]
        async def generate_stream():
            try:
                nonlocal chat_history
                full_response = ""
                
                # [核心]：LangChain 的 .stream() 方法是同步的，直接 for 循环即可
                # 传入 messages 列表，而不是单个字符串
                for chunk in llm.stream(final_messages):
                    if chunk and chunk.content:
                        content = chunk.content
                        full_response += content

                        # 按照 SSE 标准格式推送
                        yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

                # 发送结束标志
                yield f"data: {json.dumps({'done': True})}\n\n"

                # 流式输出结束后，更新 Redis 历史
                chat_history.append(HumanMessage(content=request.question))
                chat_history.append(AIMessage(content=full_response))

                max_history = 20
                if len(chat_history) > max_history:
                    chat_history = chat_history[-max_history:]
                    
                history_to_save = [
                    {"type": "human", "content": msg.content} if isinstance(msg, HumanMessage) else {"type": "ai", "content": msg.content}
                    for msg in chat_history
                ]
                session_cache.set(redis_key, json.dumps(history_to_save))
                print(f"[Stream] 回答生成完毕，历史已更新。")
            
            except Exception as e:
                traceback.print_exc()
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"辅导系统内部错误: {str(e)}")

    #     # 6. 获取最终回复并更新历史
    #     reply = current_state.get("ai_response", "哎呀，辅导老师刚才走神了，能再问一次吗？")

    #     # 7. 更新本地历史
    #     chat_history.append(HumanMessage(content=request.question))
    #     chat_history.append(AIMessage(content=reply))
        
    #     # 限制历史长度（防止内存溢出）
    #     max_history = 20
    #     if len(chat_history) > max_history:  # 假设最大保留20条
    #         chat_history = chat_history[-max_history:]
            
    #     # 将更新后的历史序列化并存入 Redis
    #     # 将 LangChain 的 Message 对象转为普通字典以便 JSON 序列化
    #     history_to_save = [
    #         {"type": "human", "content": msg.content} if isinstance(msg, HumanMessage) else {"type": "ai", "content": msg.content}
    #         for msg in chat_history
    #     ]
    #     session_cache.set(redis_key, json.dumps(history_to_save))

    #     return {"reply": reply, "session_id": session_id}

    # except Exception as e:
    #     import traceback
    #     print("\n" + "="*50)
    #     print("捕获到一个未处理的异常！详细信息如下：")
    #     print("="*50)
    #     # 这行会打印出完整的错误堆栈，告诉我们错误发生在哪个文件、哪一行
    #     traceback.print_exc()
    #     print("="*50)
    #     # --- “侦探”代码结束 ---
        
    #     # 最后，再把错误返回给前端
    #     raise HTTPException(status_code=500, detail=f"辅导系统内部错误: {str(e)}")
    
        
# 8. 启动服务
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
