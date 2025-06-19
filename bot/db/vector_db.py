from __future__ import annotations
from typing import TYPE_CHECKING, List

import logging
logger = logging.getLogger(__name__)

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
    def __init__(self, 
                 persist_directory = ".",
                 topic_merge_threshold=0.25,
                 topic_query_threshold=0.5,
                 topic_CA_period=10):
        # ChromaDB Client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        # TODO properly set this value
        # cosine distance threshold
        # when pushing, smaller than merge thres == same topic
        # when querying, smaller than query thres == same topic
        self.topic_merge_threshold = topic_merge_threshold
        self.topic_query_threshold = topic_query_threshold
        # period for Cumulative Average when combining embeddings
        self.CA_period = topic_CA_period
        
    def set_llm_client(self, LLMClient):
        self.embedding_func = MyEmbeddingFunction()
        self.embedding_func.set_openai_client(LLMClient=LLMClient)

    # push an array of data to the channel's collection
    def push(self,
             channel_id,
             documents:List[str],
             timestamps:List[List[datetime]]):
        
        # create/get collection (distance=cosine)
        collection = self.client.get_or_create_collection(
            name=f"discord_topics_{channel_id}",
            embedding_function=self.embedding_func,
            configuration={'hnsw':{'space':'cosine'}} # it is not cosine similarity -> it is cosine distance (1-cos_sim)
        )
        # loop each document
        embeddings = self.embedding_func(documents)
        document: str
        for document, embedding, (t_first,t_last) in zip(documents,embeddings,timestamps):
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
                
                if res_d < self.topic_merge_threshold:
                    no_topics_match = False
                    # concat timestamp
                    # using - "{t_first}~{t_last}" (since '~' is not used in isoformat)
                    new_timestamps = res_m['timestamps'] + ','+ \
                        f"{t_first.isoformat(timespec='minutes')}~{t_last.isoformat(timespec='minutes')}"
                    # combine embedding (Cumulative average & norm)
                    new_embedding = (res_e * self.CA_period + embedding)/(self.CA_period+1)
                    new_embedding /= np.linalg.norm(new_embedding) if sum(new_embedding) > 0 else 1
                    # update collection
                    collection.update(
                        ids=res_i,
                        embeddings=new_embedding,
                        metadatas={'timestamps':new_timestamps}
                    )
                    # debug: updated topic
                    logger.debug(f"Topic Updated: (\"{document[:50]}...\",d={res_d})")
                else:
                    # they are in distance-ascending order, 
                    # so escape once distance is too far
                    break

            # if none of the record meet the threshold, create new topic
            if no_topics_match:
                # add to collection
                collection.add(
                    ids=[str(uuid.uuid4())],
                    documents=[''],
                    embeddings=[embedding],
                    metadatas=[
                        {
                            'timestamps': 
                                f"{t_first.isoformat(timespec='minutes')}~{t_last.isoformat(timespec='minutes')}"
                        }
                    ]
                )
                # Debug: added new topic
                distances = result['distances'][0]
                logger.debug(f"New topic added: (\"{document[:50]}...\",min d={
                    min(distances) if len(distances) > 0 else 'inf'
                })")
                
        # DEBUG: # of topics
        logger.debug(f"Collection Updated ({collection.count()} topics)")

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

            # out_timstamps: List[List[[t_from,t_to]]] 
            # convert string into list of datetimes
            out_timestamps = [
                [
                    [datetime.fromisoformat(_t) for _t in _tftl.split('~')] 
                    for _tftl in meta['timestamps'].split(',')
                ]
                for _k, meta in enumerate(result['metadatas'][0]) 
                if result['distances'][0][_k] < self.topic_query_threshold*2
            ]
        except chromadb.errors.NotFoundError:
            out_timestamps = []

        # concat-ing sorted tlist by t_from
        # expected out structure: 2D List[[t_first,t_last]]
        # |<- most important topic ->           |<- second most important topic -> ...
        # |- [tf0,tl0], [tf-1,tl-1], ...(desc), | [tf0,tl0], [tf-1,tl-1], ...(desc)...
        out = []
        for tlist in out_timestamps:
            out += sorted(tlist, key=lambda t:t[0], reverse=True)

        # debug query result
        logger.debug(
            f"QueryResult:\"{query_texts[:50]}...\"\n"+\
            f"\td={result['distances'][0]}\n"+\
            f"\ttimesteps_found={len(out)}"
        )


        return out
    
