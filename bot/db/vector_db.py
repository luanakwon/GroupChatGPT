from __future__ import annotations
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings

import numpy as np
import uuid
from datetime import datetime

if TYPE_CHECKING:
    from bot.llm.llm_client import MyOpenAIClient


# my Topic DB based on ChromaDB
class Topic_VDB:
    def __init__(self, persist_directory = "."):
        # ChromaDB Client
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        # cosine similarity threshold - bigger than this thres == same topic
        self.same_topic_threshold = 0.7
        # period for Moving Average when combining embeddings
        self.MA_period = 10
        
        # Module reference
        self.LLMClient:MyOpenAIClient = None

    # push an array of data to the channel's collection
    def push(self,channel_id,documents,timestamps):
        # create/get collection (distance=cosine)
        collection = self.client.get_or_create_collection(
            name=f"discord_topics_{channel_id}",
            embedding_function=self.LLMClient.get_embedding,
            configuration={'hnsw':{'space':'cosine'}}
        )
        # loop each document
        document: str
        timestamp: datetime
        for document, timestamp in zip(documents,timestamps):
            # embed the document
            embedding = self.LLMClient.get_embedding(document)
            # query top k similar records
            result = collection.query(
                query_embeddings=embedding,
                n_results=3,
                include=['embeddings','metadatas','distances']
            )
            no_topics_match = True
            for i in range(3):
                # if any of the record are similar enough, combine into the existing topic
                if result['distances'][i] < self.same_topic_threshold:
                    no_topics_match = False
                    # concat timestamp
                    new_timestamps = result['metadatas'][i]['timestamps'] + ','+ timestamp.isoformat(timespec='seconds')
                    # combine embedding (Moving average & norm)
                    new_embedding = (result['embeddings'][i] * self.MA_period + embedding)/(self.MA_period+1)
                    new_embedding /= np.linalg.norm(new_embedding) if sum(new_embedding) > 0 else 1
                    # update collection
                    collection.update(
                        ids=result['ids'][i],
                        embeddings=new_embedding,
                        metadatas={'timestamps':new_timestamps}
                    )
                else:
                    # they are in distance-ascending order, 
                    # so escape once distance is too far
                    break

            # if none of the record meet the threshold, create new topic
            if no_topics_match:
                collection.add(
                    ids=[str(uuid.uuid4())],
                    documents=[''],
                    embeddings=[embedding],
                    metadatas=[{'timestamps':timestamp.isoformat(timespec='seconds')}],
                )

    def query(self, channel_id, query_texts, k):
        # get collection for the channel id
        collection = self.client.get_collection(
            name=f"discord_topics_{channel_id}",
            embedding_function=self.LLMClient.get_embedding
        )
        # query top k results
        result = collection.query(
            query_texts=query_texts,
            n_results=k,
            include=['metadatas', 'distances']
        )
        
        # convert string into list of datetimes
        out_timestamps = [
            [datetime.fromisoformat(_t) for _t in meta['timestamps'].split(',')]
            for i, meta in enumerate(result['metadatas']) 
            if result['distances'][i] > self.same_topic_threshold
        ]
        out = []
        for tlist in out_timestamps:
            out += sorted(tlist,reverse=True)

        # expected out structure: 1D list[datetime]
        # |<- most important topic -> |<- second most important topic -> ...
        # |- t0, t-1, t-2, ...(desc), | t0, t-1, t-2, ...(desc)...
        return out
    
