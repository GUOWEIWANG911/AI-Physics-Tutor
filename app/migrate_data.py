import sqlite3
import json

def migrate_json_to_sqlite(json_path, db_path):
    # 1. 读取 JSON 数据
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # 2. 连接 SQLite 并创建表
    conn = sqlite3.connect(db_path)
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

    # 3. 将数据插入 SQLite
    for entry in data:
        # 注意：retrieved_docs 在 JSON 中是列表，存入 SQLite 时可转为字符串
        docs_str = json.dumps(entry.get('retrieved_docs', []), ensure_ascii=False)

        cur.execute('''
            INSERT INTO learning_history(timestamp, query, retrieved_docs, llm_answer, feedback)
            VALUES(?,?,?,?,?)
        ''',(
            entry.get('timestamp'),
            entry.get('query'),
            docs_str,
            entry.get('llm_answer'),
            entry.get('feedback')
        ))

    conn.commit()
    conn.close()
    print(f"成功将 {len(data)} 条记录从 JSON 迁移至 SQLite!")

# 执行任务
migrate_json_to_sqlite('learning_history.json', 'learning_history.db')