import sqlite3
import os

class MemoryStorage:
    def __init__(self, db_path="agent_memory.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS memories
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      content TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()

    def remember(self, text: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO memories (content) VALUES (?)", (text,))
        conn.commit()
        conn.close()
        return "I have remembered this."

    def recall(self, query: str = None):
        """Simple retrieval. A more advanced one would use embedding search."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if query:
            # simple wildcard matching
            c.execute("SELECT content FROM memories WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 5", (f"%{query}%",))
        else:
            c.execute("SELECT content FROM memories ORDER BY timestamp DESC LIMIT 5")
            
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return "I don't have any memories related to that."
        
        memories = "\n".join([row[0] for row in rows])
        return memories
