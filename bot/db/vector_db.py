
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
    

        