# 1. 导入配置文件
import os
import re
import time
import sqlite3
from config import CHROMA_DB_PATH, TEXTBOOK_FILES, TEXTBOOK_MAPPING
from config import LEARNING_DB_PATH

from llm_factory import get_llm
from embedding_factory import get_embedding
from tracker import LearningTracker
from redis_smart_cache import SmartCache
from meta_agent import meta_analysis_agent

from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.documents import Document
# from langchain_unstructured import UnstrcturedImageLoader

# 1. 记忆管理智能体（Memory Agent）
def memory_agent(state, llm):
    """
    职责：整理历史对话，生成“学情摘要”，防止Token爆炸
    如果对话轮数少，直接透传；如果轮数多，让LLM总结
    """
    history = state.get("history", [])
    user_question = state["user_question"]

    # 简单策略：如果历史记录超过 6 条（3轮对话），则进行总结压缩
    if len(history) > 6:
        summary_prompt = f"""请根据以下对话历史，用1~2句话总结学生的[当前学习状态]和[知识掌握情况]。
        对话历史：{history}
        当前问题：{user_question}
        只输出总结，不要输出其他废话。"""

        summary_response = llm.invoke([HumanMessage(content=summary_prompt)])
        state["student_summary"] = summary_response.content
    else:
        state["student_summary"] = "这是对话的开始，暂无历史学情摘要"

    return state

def clean_question_for_cache(question: str) -> str:
    """
    对问题进行标准化清洗，最大化缓存命中率
    """
    if not question:
        return ""
    # 1. 统一转小写（避免 "What" 和 "what" 被当成两个问题）
    cleaned = question.lower()
    # 2. 去除首尾空格
    cleaned = cleaned.strip()
    # 3. 将所有的连续空白字符（包括空格、换行、Tab）替换为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # 4. 去除所有标点符号（中英文标点都会被剔除）
    # 比如 "什么是升华？" 和 "什么是升华!" 都会变成 "什么是升华"
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    
    return cleaned

# 2. 知识检索智能体（Retrieval Agent）
def retrieval_agent(state, vectorstore, cache_manager, reranker_model):
    """
    职责：结合“学情摘要”和“当前问题”，去向量库精准找资料。
    优先从缓存获取，避免重复检索和 Rerank 消耗
    """
    user_question = state["user_question"]
    student_summary = state.get("student_summary", "")

    # [优化 1]：使用纯粹的“用户问题”作为缓存 Key，避免学情摘要变化导致缓存失效
    # cache_key = f"retrieval:{user_question}"
    cleaned_question = clean_question_for_cache(user_question)
    cache_key = f"retrieval:{cleaned_question}"

    # 尝试从缓存获取检索结果
    cache_context = cache_manager.get(cache_key)
    if cache_context:
        # 命中缓存，直接返回，不再打印未命中日志
        state["retrieved_context"] = cache_context
        return state

    print("[Retrieval] 缓存未命中，正在检索知识库...")

    total_start_time = time.perf_counter()

    # 把摘要和问题拼接，作为一个更丰富的查询词
    search_query = f"学情背景：{student_summary}, 学生当前问题：{user_question}"

    # [阶段一：初步召回]
    # 先把 k 调大（比如 10），尽可能多地捞出可能相关的候选内容，防止漏掉正确答案
    step1_start = time.perf_counter()
    candidate_docs = vectorstore.similarity_search(
        search_query, 
        k=8,
        score_threshold=0.6  # 过滤低相关文档
    )
    print(f"   ⏱️ [阶段一: 向量召回] 耗时: {time.perf_counter() - step1_start:.3f}秒")

    # [阶段二：Rerank 重排]
    # 将查询词和每个候选文档组成对（pairs）
    step2_start = time.perf_counter()
    pairs = [[search_query, doc.page_content] for doc in candidate_docs]
    # 模型进行批量打分，加上 convert_to_numpy=True，确保在 GPU 推理后安全返回分数
    scores = reranker_model.predict(pairs, batch_size=32, convert_to_numpy=True)
    print(f"   ⏱️ [阶段二: Rerank重排] 耗时: {time.perf_counter() - step2_start:.3f}秒")

    # 将文档和分数打包，按分数从高到底排序，取前 3 个
    scored_docs = sorted(zip(candidate_docs, scores), key=lambda x: x[1], reverse=True)
    reranked_docs = [doc for doc, score in scored_docs[:3]]

    # 构建结构化证据列表（供 Tutor Agent 标注使用）
    retrieved_items = []
    for doc in reranked_docs:
        # 安全提取元数据（防止 KeyError）
        source = doc.metadata.get("source", "苏教版物理")
        page = doc.metadata.get("page", 0)
        
        try:
            page_num = int(doc.metadata.get("page", 1))
        except (ValueError, TypeError):
            page_num = "未知"
            
        retrieved_items.append({
            "content": doc.page_content,
            "source": source,
            "page": f"第{page_num}页"
        })

    # 将结构化数据存入 state（关键！）
    state["retrieved_evidence"] = retrieved_items

    # 将重排后的结果拼接成上下文
    # context = "\n\n".join([doc.page_content for doc in reranked_docs])
    context = "\n\n".join([item["content"] for item in retrieved_items])

    # 将检索结果存入缓存
    cache_manager.set(cache_key, context)
    print(f"[Cache] 检索结果已写入缓存，Key: {cache_key}")
    
    # 记录整个检索流程的结束时间，并打印总耗时
    print(f"✅ [Retrieval] 检索与重排全部完成！总耗时: {time.perf_counter() - total_start_time:.3f}秒")

    state["retrieved_context"] = context
    return state


# 3. 辅导老师智能体（Tutor Agent）
def tutor_agent(state, llm):
    """
    职责：专心扮演老师，结合资料和历史，启发学生
    """
    # . 获取结构化证据（用于生成标注）
    evidence = state.get("retrieved_evidence", [])

    # 2. 获取纯文本上下文（用于知识理解，保持不变）
    context = state.get("retrieved_context", "")
    student_summary = state.get("student_summary", "")
    user_question = state["user_question"]
    history = state.get("history", [])

    dynamic_strategies = state.get("dynamic_strategies", "")

    # 动态生成标注指令（关键！）
    citation_instruction = ""
    if evidence:
        # 取最相关的一条作为标注模板
        top_evidence = evidence[0]
        citation_instruction = f"""
【教材标注强制要求】：
- 回答中涉及知识点时，必须在句末标注来源。
- 标注格式严格为：**（来源：{top_evidence['source']} {top_evidence['page']}）**
- 示例："根据光的干涉原理，当光程差为波长整数倍时出现明条纹**（来源：{top_evidence['source']} {top_evidence['page']}）**"
- 若当前问题无法从教材中找到依据，请明确告知学生"教材暂未收录此内容"，严禁编造。
"""
    else:
        citation_instruction = """
【教材标注要求】：
- 当前未检索到教材依据，请基于通用物理知识回答，但需注明"此回答未找到教材原文支持"。
"""

    # 组装 System Pormpt
    system_prompt = f"""你是一个初中理科辅导老师。
【当前学情】：{student_summary}
【参考资料】：{context}
{citation_instruction}
【辅导要求】：
1. 优先使用启发式提问，严禁直接给答案，严禁超纲。
2. 必须结合【历史对话】上下文，不要重复提问，不要答非所问。
3. 如果学生明确表示“直接告诉我”或连续2次困惑，立刻停止提问，直接给步骤和答案。

{dynamic_strategies}

请根据以上原则和历史教训，回答学生的问题。
"""
     
    messages = [SystemMessage(content=system_prompt)]
    messages.extend(history)
    messages.append(HumanMessage(content=user_question))

    # response = llm.invoke(messages)
    # state["ai_response"] = response.content
     # 2. 【关键修改】：不再调用 llm.invoke(messages)
    # 而是把组装好的 messages 存入 state，留给 /ask 接口去流式输出
    state["messages"] = messages  

    return state


def build_knowledge_base(file_paths, embeddings):
    db_path = CHROMA_DB_PATH
    
    all_documents = []

    if os.path.exists(db_path):
        print("检测到本地已有知识库，正在直接加载（本次不消耗任何API额度）...")
        try:
            vectorstore = Chroma(persist_directory=db_path, embedding_function=embeddings)
            # 验证一下里面是否有数据，防止空库加载
            count = vectorstore._collection.count()
            if count > 0:
                return vectorstore
            else:
                print("警告：数据库存在但为空，将重新构建...")
        except Exception as e:
            print(f"加载现有数据库出错: {e}，将尝试重建...")
    
    print("开始构建知识库...")
    
    # 循环读取每一个文件
    for file_path in TEXTBOOK_FILES:
        try:
            # 使用 PyPDFLoader 来读取 PDF 文件
            loader = PyPDFLoader(file_path)
            documents = loader.load()

            # 通过映射表注入教材版本
            filename = os.path.basename(file_path)
            # 从配置映射表获取人类可读标识（若未配置则回退到文件名）
            human_readable_source = TEXTBOOK_MAPPING.get(
                filename, 
                filename.replace(".pdf", "")  # 安全回退
            )
            
            for doc in documents:
                # 注入修正后的教材标识（不再是原始路径）
                doc.metadata["source"] = human_readable_source
                # 修正页码：0-based → 1-based（人类可读）
                doc.metadata["page"] = doc.metadata.get("page", 0) + 1

            all_documents.extend(documents)
            print(f"成功加载文件：{file_path}")
        except Exception as e:
            print(f"加载文件 {file_path} 失败：{e}")

    if not all_documents:
        raise ValueError("没有成功加载任何文档，请检查 PDF 路径是否正确！")

    # 文本分块
    text_splitter = RecursiveCharacterTextSplitter(chunk_size = 500, chunk_overlap = 50)
    chunks = text_splitter.split_documents(all_documents)
    print(f"【调试信息】文本分块完成，共 {len(chunks)} 个片段，准备开始生成向量...")

    # # 生成向量数据库
    # vectorstore = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=db_path)
    # print(f"知识库构建完成! 共包含{len(chunks)} 个知识片段")
    print("【调试信息】正在手动为文本片段生成向量...")
    # 1. 先提取所有文本
    texts = [chunk.page_content for chunk in chunks]

    batch_size = 64
    embeddings_list = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = embeddings.embed_documents(batch)
        embeddings_list.extend(batch_embeddings)
        print(f"【调试信息】已生成 {len(embeddings_list)}/{len(texts)} 个向量")

    print(f"【调试信息】向量生成完成，共 {len(embeddings_list)} 个向量。")

    # 3. 创建一个空的 Chroma 实例
    vectorstore = Chroma(
        embedding_function=embeddings, 
        persist_directory=db_path
    )

    # 4. 手动将文本和对应的向量添加进去
    print("【调试信息】正在将文本和向量添加到数据库...")
    # vectorstore.add_texts(texts=texts, embeddings=embeddings_list)
    vectorstore._collection.add(
        ids=[f"doc_{i}" for i in range(len(texts))],
        documents=texts,
        embeddings=embeddings_list,
        metadatas=[chunk.metadata for chunk in chunks]  # 保留原始 metadata
    )
    print("【调试信息】知识库构建完成！")
        
    return vectorstore


# 获取差评并生成策略的辅助函数
def get_dynamic_strategies():
    """从数据库获取最近的差评，并让 Meta-Agent 生成策略"""

    db_file = LEARNING_DB_PATH

    if not os.path.exists(db_file):
        print(f"[策略] 未找到数据库文件: {db_file}，跳过策略生成。")
        return ""
    
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute('''
            SELECT query, llm_answer FROM learning_history 
            WHERE feedback = 'negative' 
            ORDER BY timestamp DESC LIMIT 5
        ''')
        negative_records = [{"query": row[0], "llm_answer": row[1]} for row in cur.fetchall()]
        conn.close()
        if not negative_records:
            return ""  # 没有差评，返回空字符串
            
        # 调用 Meta-Agent 生成策略
        strategies = meta_analysis_agent(negative_records)
        return f"\n\n[历史教训与改进策略(必须严格遵守)]：\n{strategies}"
    
    except Exception as e:
        print(f"[策略] 读取数据库失败: {e}")
        return ""
