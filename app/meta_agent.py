from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm_factory import get_llm

llm = get_llm()

def meta_analysis_agent(negative_records):
    """
    元分析智能体：分析差评记录，提炼教学改进策略
    """
    # 1. 构造供分析的差评数据
    bad_cases = "\n".join([f"问题: {r['query']}\nAI回答: {r['llm_answer']}" for r in negative_records])

    # 2. 设计 Meta-Agent 的提示词
    meta_prompt = ChatPromptTemplate.from_template("""
    你是以为资深的物理教研组长。以下是以为AI辅导老师最近收到的[差评记录]。
    请分析这些回答为什么没能帮到学生，并总结出 3 条具体的、可执行的[教学改进策略]。
    注意：策略必须具体，例如“解释惯性时必须用公交车刹车举例”，而不是“要生动形象”。
                                                  
    【差评记录】：
    {bad_cases}
                                                  
    【请输出改进策略】（直接输出策略列表，不要多余的废话）：
    """)

    # 3. 调用 LLM 生成策略
    chain = meta_prompt | llm | StrOutputParser()
    strategies = chain.invoke({"bad_cases": bad_cases})

    return strategies