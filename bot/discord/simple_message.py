import datetime
import json

class SimpleMessage:
    def __init__(
            self, 
            author='anonymous', 
            created_at=datetime.datetime.now(datetime.timezone.utc), 
            content=''):
        self.author: str = author
        self.created_at: datetime.datetime = created_at
        self.content:str = content

    def toJSON(self):
        dict_obj = {
            'author':self.author,
            'created_at':self.created_at.isoformat(timespec='seconds'),
            'content':self.content
        }
        return json.dumps(dict_obj)
