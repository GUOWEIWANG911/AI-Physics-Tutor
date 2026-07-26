import os
import time
import config
import logging

logger = logging.getLogger(__name__)

def async_log_llm_performance(func):
    """LLM 性能监控装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        # LangChain AIMessage 的 Token 信息在 response_metadata 里
        usage = getattr(result, 'response_metadata', {}).get('usage', {})
        input_tokens = usage.get('prompt_tokens', 'N/A')
        output_tokens = usage.get('completion_tokens', 'N/A')
        total_tokens = usage.get('total_tokens', 'N/A')

        logger.info(
            f"📊 LLM 调用耗时: {elapsed:.2f}s | "
            f"输入: {input_tokens} | 输出: {output_tokens} | 总计: {total_tokens}"
        )
        return result
    return wrapper


# 创建一个全局变量来“缓存”LLM实例
_llm_instance = None

def get_llm():
    """
    工厂函数：确保全局只有一个LLM实例（单例模式）
    """

    global _llm_instance # 声明我们要使用全局的那个缓存变量

    # 如果缓存里已经有了，直接返回，不再重复创建
    if _llm_instance is not None:
        return _llm_instance

    print(f"正在初始化 LLM 模型：{config.LLM_PROVIDER}")
    
    if config.LLM_PROVIDER == "zhipu":
        from langchain_community.chat_models import ChatZhipuAI
        zhipu_llm_config = {**config.MODELS["zhipu"]["llm"], "api_key" : config.ZHIPUAI_API_KEY}
        _llm_instance = ChatZhipuAI(**zhipu_llm_config)
        
    elif config.LLM_PROVIDER == "deepseek":
        from langchain_deepseek import ChatDeepSeek
        deepseek_llm_config = {**config.MODELS["deepseek"]["llm"], "api_key" : config.DEEPSEEK_API_KEY}
        _llm_instance = ChatDeepSeek(**deepseek_llm_config)
        
    elif config.LLM_PROVIDER == "qwen":
        from langchain_community.chat_models import ChatTongyi
        qwen_llm_config = {**config.MODELS["qwen"]["llm"], "dashscope_api_key" : config.DASHSCOPE_API_KEY}
        _llm_instance = ChatTongyi(**qwen_llm_config)
        
    else:
        raise ValueError(f"不支持的 LLM 供应商：{config.LLM_PROVIDER}")
    
    return _llm_instance