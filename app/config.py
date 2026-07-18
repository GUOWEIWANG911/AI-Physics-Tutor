import os
from dotenv import load_dotenv

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

load_dotenv()

ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# 1. 获取当前文件(config.py)所在的绝对路径 (即 app/ 目录)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 获取项目根目录 (即 MyAgent/ 目录，也就是 app 的上一级)
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# 向量数据库路径：指向根目录下的 data/chroma_db
CHROMA_DB_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_db")

# 教材路径：指向根目录下的 data/textbooks
TEXTBOOK_DIR = os.path.join(PROJECT_ROOT, "data", "textbooks")

# 本地模型路径：指向根目录下的 models
RERANKER_MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "bge-reranker-v2-m3") 

# 指向根目录下的 data/learning_history.db
LEARNING_DB_PATH = os.path.join(PROJECT_ROOT, "data", "learning_history.db")

# ================== 模型选择 ==================
# 可选值："zhipu", "deepseek", "qwen"
EMBEDDING_PROVIDER = "zhipu"
LLM_PROVIDER = "deepseek"

# ================== 模型参数 ==================
# 对话记忆保留的最大轮数 （一问一答算2条消息）
MAX_HISTORY_MESSAGES = 10

MODELS = {
    "zhipu": {
        "embedding": {"model": "embedding-3"},
        "llm": {"model": "glm-4", "temperature": 0.7}
    },
    "deepseek": {
        "embedding": {"model": "deepseek-embedding-v3", "base_url": "https://api.deepseek.com/v1"},
        "llm": {"model": "deepseek-chat", "temperature": 0.7}
    },
    "qwen": {
        "embedding": {"model": "text-embedding-v3", "base_url": "https://dashscope.aliyuncs.com/compatible-model/v1"},
        "llm": {"model": "qwen-plus", "temperature": 0.7}
    }
}

# 这里列出所有需要加载的教材文件名，程序会自动拼接成完整路径
TEXTBOOK_FILES = [
    os.path.join(TEXTBOOK_DIR, "physics_8a.pdf"),
    os.path.join(TEXTBOOK_DIR, "physics_8b.pdf"),
    os.path.join(TEXTBOOK_DIR, "physics_9a.pdf"),
    os.path.join(TEXTBOOK_DIR, "physics_9b.pdf"),
]

TEXTBOOK_MAPPING = {
    # 格式: "英文文件名": "人类可读的教材标识"
    "physics_8a.pdf": "苏教版物理八年级上册",
    "physics_8b.pdf": "苏教版物理八年级下册",
    "physics_9a.pdf": "苏教版物理九年级上册",
    "physics_9b.pdf": "苏教版物理九年级下册",
}