import sqlite3
import json
from datetime import datetime

from config import LEARNING_DB_PATH

class LearningTracker:
    def __init__(self, db_name=LEARNING_DB_PATH):
        self.db_name = db_name
        # 在内存中暂存本轮对话的所有记录，用于退出时回顾
        self.current_session_history = []
        # 兼容原代码中 self.history 属性
        self.history = []
        self._init_db()

    def _init_db(self):
        """初始化数据库和表结构"""
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS learning_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                query TEXT,
                retrieved_docs TEXT,
                llm_answer TEXT,
                feedback TEXT    
            ) 
        ''')
        conn.commit()
        conn.close()


    def log_interaction(self, query, retrieved_docs, llm_answer, feedback=None):
        """记录一次完整的交互"""
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()

        # 将列表转换为 JSON 字符串存入数据库
        docs_str = json.dumps(retrieved_docs[:3], ensure_ascii=False)

        cur.execute('''
            INSERT INTO learning_history (timestamp, query, retrieved_docs, llm_answer, feedback)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            query,
            docs_str,
            llm_answer,
            feedback
        ))
        conn.commit()
        # 获取刚刚插入数据库的记录 ID
        record_id = cur.lastrowid
        conn.close()

        # 同步更新到内存中，方便最后退出时回顾
        self.current_session_history.append({
            "id": record_id,
            "query": query,
            "llm_answer": llm_answer,
            "feedback": feedback
        })    

        # 保持兼容：也追加到 self.history 中
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "retrieved_docs": retrieved_docs[:3],
            "llm_answer": llm_answer,
            "feedback": feedback
        })

    def update_feedback(self, query_timestamp, feedback):
        """根据时间戳更新某次交互的反馈（保持原有接口不变）"""
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute('''
            UPDATE learning_history SET feedback = ? WHERE timestamp = ?
        ''', (feedback, query_timestamp))
        conn.commit()
        # 检查是否真的有数据被更新
        success = cur.rowcount > 0 
        conn.close()
        
        # 同步更新内存中的记录
        if success:
            for record in self.current_session_history:
                if record["query"] == query_timestamp.split("T")[0]: 
                    # 简单匹配，或者你可以用更精确的方式
                    pass
        return success
    
    def update_feedback_by_id(self, record_id, feedback):
        """根据 ID 更新反馈（专为退出回顾设计，更精准）"""
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute('''
            UPDATE learning_history SET feedback = ? WHERE id = ?
        ''', (feedback, record_id))
        conn.commit()
        conn.close()
        
        # 同步更新内存中的记录
        for record in self.current_session_history:
            if record["id"] == record_id:
                record["feedback"] = feedback
                break

    def review_and_collect_feedback(self):
        """退出时统一回顾并收集反馈"""
        if not self.current_session_history:
            return

        print("\n" + "="*50)
        print("辅导回顾：我们来快速回顾一下今天的学习吧！")
        print("="*50)

        for record in self.current_session_history:
            # 只回顾那些还没有反馈的记录
            if not record["feedback"]:
                print(f"\n问题：{record['query']}")
                # 简单展示回答的前60个字，防止太长
                answer_preview = record['llm_answer'][:60].replace('\n', ' ')
                print(f"回答：{answer_preview}...") 
                feedback_input = input("这个解答对你有帮助吗？(y/n/回车跳过): ").strip().lower()
                
                if feedback_input in ["y", "yes"]:
                    self.update_feedback_by_id(record["id"], "positive")
                    print("已记录为【有帮助】")
                elif feedback_input in ["n", "no"]:
                    self.update_feedback_by_id(record["id"], "negative")
                    print("已记录为【没帮助】")
                else:
                    print("已跳过")
        
        print("\n" + "="*50)
        print("感谢你的反馈！这对我的成长非常重要。")
        print("="*50)
