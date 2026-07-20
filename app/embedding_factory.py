import os
import config

# 创建一个全局变量来“缓存”LLM实例
_embedding_instance = None

def get_embedding():
    """
    工厂函数：根据配置返回初始化好的 Embedding 实例
    """

    global _embedding_instance # 声明我们要使用全局的那个缓存变量

    # 如果缓存里已经有了，直接返回，不再重复创建
    if _embedding_instance is not None:
        return _embedding_instance

    print(f"正在初始化 Embeddign 模型：{config.EMBEDDING_PROVIDER}")
    if config.EMBEDDING_PROVIDER == "zhipu":
        from langchain_community.embeddings import ZhipuAIEmbeddings
        _embedding_instance = ZhipuAIEmbeddings(**config.MODELS["zhipu"]["embedding"])

    elif config.EMBEDDING_PROVIDER == "deepseek":
        from langchain_openai import OpenAIEmbeddings
        deepseek_emb_config = {**config.MODELS["deepseek"]["embedding"], "openai_api_key" : config.DEEPSEEK_API_KEY}
        _embedding_instance = OpenAIEmbeddings(**deepseek_emb_config)

    elif config.EMBEDDING_PROVIDER == "qwen":
        from langchain_openai import OpenAIEmbeddings
        qwen_emb_config = {**config.MODELS["qwen"]["embedding"], "openai_api_key" : config.DASHSCOPE_API_KEY}
        _embedding_instance = OpenAIEmbeddings(**qwen_emb_config)
    else:
        raise ValueError(f"不支持的 Embedding 提供商：{config.EMBEDDING_PROVIDER}")
    
    return _embedding_instance