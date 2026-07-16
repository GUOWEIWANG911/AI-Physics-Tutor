import os
import config

def get_embedding():
    """
    工厂函数：根据配置返回初始化好的 Embedding 实例
    """
    print(f"正在初始化 Embeddign 模型：{config.EMBEDDING_PROVIDER}")
if config.EMBEDDING_PROVIDER == "zhipu":
    from langchain_community.embeddings import ZhipuAIEmbeddings
    embeddings = ZhipuAIEmbeddings(**config.MODELS["zhipu"]["embedding"])

elif config.EMBEDDING_PROVIDER == "deepseek":
    from langchain_openai import OpenAIEmbeddings
    deepseek_emb_config = {**config.MODELS["deepseek"]["embedding"], "openai_api_key" : config.DEEPSEEK_API_KEY}
    embeddings = OpenAIEmbeddings(**deepseek_emb_config)

elif config.EMBEDDING_PROVIDER == "qwen":
    from langchain_openai import OpenAIEmbeddings
    qwen_emb_config = {**config.MODELS["qwen"]["embedding"], "openai_api_key" : config.DASHSCOPE_API_KEY}
    embeddings = OpenAIEmbeddings(**qwen_emb_config)
else:
    raise ValueError(f"不支持的 Embedding 提供商：{config.EMBEDDING_PROVIDER}")