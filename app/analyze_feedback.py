import sqlite3
import json
from collections import Counter

def analyze_learning_history(db_name="learning_history.db"):
    """分析 SQLite 中的学习历史数据"""
    try:
        conn = sqlite3.connect(db_name)
        cur = conn.cursor()

        # 1. 获取总交互次数
        cur.execute("SELECT COUNT(*) FROM learning_history")
        total_interactions = cur.fetchone()[0]

        if total_interactions == 0:
            print("数据库中暂无学习记录。")
            return
        
        # 2. 统计反馈情况（Positive / Negative / 未反馈）
        cur.execute("SELECT feedback, COUNT(*) FROM learning_history GROPU BY feedback")
        feedback_stats = cur.fetchall()

        # 将统计结果转化为字典方便处理
        feedback_dict = {row[0] or "pending": row[1] for row in feedback_stats}
        positive_count = feedback_dict.get("positive", 0)
        negative_count = feedback_dict.get("negative", 0)
        pending_count = feedback_dict.get("pending", 0)

        # 3. 找出差评最多的问题（Top 3）
        cur.execute('''
            SELECT query, llm_answer, COUNT(*) as bad_count 
            FROM learning_history 
            WHERE feedback = 'negative' 
            GROUP BY query 
            ORDER BY bad_count DESC 
            LIMIT 3
        ''')
        top_negative = cur.fetchall()

        # 4. 打印分析报告
        print("="*60)
        print("辅导 Agent 学情数据分析报告")
        print("="*60)
        print(f"总交互次数: {total_interactions}")
        print(f"有帮助 (Positive): {positive_count}")
        print(f"没帮助 (Negative): {negative_count}")
        print(f"待反馈 (Pending): {pending_count}")

        if positive_count + negative_count > 0:
            satisfaction_rate = positive_count / (positive_count + negative_count) * 100
            print(f"用户满意度: {satisfaction_rate:.2f}%")
        print("-"*60)

        if top_negative:
            print("差评最多的问题 (Top 3):")
            for i, (query, answer, count) in enumerate(top_negative, 1):
                print(f"{i}. 问题: {query}")
                print(f"   回答预览: {answer[:50]}...")
                print(f"   差评次数: {count}")
        else:
            print("太棒了！目前没有差评记录。")
        
        print("="*60)

    except sqlite3.Error as e:
        print(f"数据库读取失败：{e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    analyze_learning_history()
