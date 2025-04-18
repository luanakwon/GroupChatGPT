import sqlite3
from datetime import datetime

class ChannelMemoryDB:
    def __init__(self, db_path='channel_memory.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS channel_memory (
                    channel_id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    summary TEXT
                )
            """)
            con.commit()

    def get_memory(self,channel_id:int):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT timestamp, summary FROM channel_memory
                WHERE channel_id = ?
            """,(channel_id,))
            row = cur.fetchone()
            return row if row else None

    def set_memory(self,channel_id:int,timestamp:str,summary:str):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO channel_memory (channel_id, timestamp, summary)
                VALUES (?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    summary = excluded.summary
            """, (channel_id, timestamp, summary))
            con.commit()
            