from __future__ import annotations
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings
from chromadb import Documents, EmbeddingFunction, Embeddings

import chromadb.errors
import numpy as np
import uuid
from datetime import datetime

if TYPE_CHECKING:
    from bot.llm.llm_client import MyOpenAIClient


class MyEmbeddingFunction(EmbeddingFunction):
    def set_openai_client(self,LLMClient:MyOpenAIClient):
        self.LLMClient = LLMClient
    def __call__(self, texts: Documents) -> Embeddings:
        return self.LLMClient.get_embedding(texts)

# my Topic DB based on ChromaDB
class Topic_VDB:
    def __init__(self, persist_directory = "."):
        # ChromaDB Client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        # cosine similarity threshold - bigger than this thres == same topic
        self.same_topic_threshold = 0.55
        # period for Moving Average when combining embeddings
        self.MA_period = 10
        
    def set_llm_client(self, LLMClient):
        self.embedding_func = MyEmbeddingFunction()
        self.embedding_func.set_openai_client(LLMClient=LLMClient)

    # push an array of data to the channel's collection
    def push(self,channel_id,documents,timestamps):
        # create/get collection (distance=cosine)
        collection = self.client.get_or_create_collection(
            name=f"discord_topics_{channel_id}",
            embedding_function=self.embedding_func,
            configuration={'hnsw':{'space':'cosine'}}
        )
        # loop each document
        embeddings = self.embedding_func(documents)
        document: str
        timestamp: datetime
        for document, embedding, timestamp in zip(documents,embeddings,timestamps):
            # query top k similar records
            result = collection.query(
                query_embeddings=embedding,
                n_results=3,
                include=['embeddings','metadatas','distances']
            )
            no_topics_match = True
            for res_i, res_d, res_e, res_m in zip(
                    result['ids'][0],
                    result['distances'][0],
                    result['embeddings'][0],
                    result['metadatas'][0]):
                # if any of the record are similar enough, combine into the existing topic
                print(res_d)
                if res_d > self.same_topic_threshold:
                    no_topics_match = False
                    # concat timestamp
                    new_timestamps = res_m['timestamps'] + ','+ timestamp.isoformat(timespec='seconds')
                    # combine embedding (Moving average & norm)
                    new_embedding = (res_e * self.MA_period + embedding)/(self.MA_period+1)
                    new_embedding /= np.linalg.norm(new_embedding) if sum(new_embedding) > 0 else 1
                    # update collection
                    collection.update(
                        ids=res_i,
                        embeddings=new_embedding,
                        metadatas={'timestamps':new_timestamps}
                    )
                    print(f"\n\n\nupdated collection {document}\n\n\n")
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
                print(f"\n\n\nadded to collection {document}\n\n\n")

    def query(self, channel_id, query_texts, k):
        try:
            # get collection for the channel id
            collection = self.client.get_collection(
                name=f"discord_topics_{channel_id}",
                embedding_function=self.embedding_func
            )
            # query top k results
            result = collection.query(
                query_texts=query_texts,
                n_results=k,
                include=['metadatas', 'distances']
            )
            
            print(result['distances'][0])

            # convert string into list of datetimes
            out_timestamps = [
                [datetime.fromisoformat(_t) for _t in meta['timestamps'].split(',')]
                for i, meta in enumerate(result['metadatas'][0]) 
                if result['distances'][0][i] > self.same_topic_threshold*0.5
            ]
        except chromadb.errors.NotFoundError as e:
            out_timestamps = []

        out = []
        for tlist in out_timestamps:
            out += sorted(tlist,reverse=True)

        # expected out structure: 1D list[datetime]
        # |<- most important topic -> |<- second most important topic -> ...
        # |- t0, t-1, t-2, ...(desc), | t0, t-1, t-2, ...(desc)...
        return out
    
