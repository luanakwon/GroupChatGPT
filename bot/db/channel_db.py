import logging
logger = logging.getLogger(__name__)

import sqlite3

class ChannelTimestampDB:
    def __init__(self, db_path='channel_timestamp.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS channel_timestamp (
                    channel_id INTEGER PRIMARY KEY,
                    timestamp TEXT
                )
            """)
            con.commit()
        logger.info('DB initialized')

    def get_memory(self,channel_id:int)->str|None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT timestamp FROM channel_timestamp
                WHERE channel_id = ?
            """,(channel_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def set_memory(self,channel_id:int,timestamp:str):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO channel_timestamp (channel_id, timestamp)
                VALUES (?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    timestamp = excluded.timestamp
            """, (channel_id, timestamp))
            con.commit()
            