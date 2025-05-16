import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from bot.config.credentials import OPENAI_API_KEY

import numpy as np
import uuid


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

        self.embedding_func = OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name='text-embedding-3-small'
        )
        self.LLMClient = None

    # push an array of data to the channel's collection
    def push(self,channel_id,documents,metadatas):
        # create/get collection (distance=cosine)
        collection = self.client.get_or_create_collection(
            name=f"discord_topics_{channel_id}",
            configuration={'hnsw':{'space':'cosine'}}
        )
        # loop each document
        for document, timestamp in zip(documents,metadatas):
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
                    new_timestamps = result['metadatas'][i]['timestamps'] + ','+str(timestamp)
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
                    metadatas=[{'timestamps':str(timestamp)}],
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
            include=['metadatas']
        )
        # convert string into list of time-strings
        out_timestamps = [meta['timestamps'].split(',') for meta in result['metadatas']]
        return out_timestamps
    






# # pseudo-code
# class Topic_VectorStorage:
#     ...
#     # push to the storage
#     def push(self, message, timestamp):
#         # iterate through topics
#         for record in self.topic_db:
#             # get similarity score with the existing topic(record) 
#             sim_score = similarity(
#                 embedded(message),
#                 record.embed
#             )
#             # if they are similar enough
#             if sim_score > combine_threshold:
#                 # append message to the topic (using timestamp)
#                 record.timestamps.append(timestamp)
#                 # update topic by moving average
#                 record.embed = (record.embed*n + embedded(message))/(n+1)
        
#         # no topics are similar enough
#         if no_topics_match:
#             # create new topic and store
#             self.topic_db.append(
#                 Record(
#                     embedded(message),
#                     timestamp
#                 )
#             )

#     def top_k(self,message):
#         top_k_records = get_similar_topics_record(message)
#         timestamps = []
#         for record in top_k_records:
#             timestamps += record.timestamps
#         return timestamps
    

        