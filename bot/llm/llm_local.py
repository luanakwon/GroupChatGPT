import logging
logger = logging.getLogger(__name__)

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

class EmbeddingLM:
    def __init__(self,model_id, device='cpu'):
        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            trust_remote=False)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=False)
        self.model.eval()
        if device != 'cpu':
            raise NotImplementedError("devices other than 'cpu' are not implemented.")
        self.model.to(device)

    def get_embedding(self, prompts):
        filtered_prompts = [text for text in prompts if len(text) > 0]
        if len(prompts) != len(filtered_prompts):
            # print(f"from get_embedding - unexpected empty string found in {prompts}")
            logger.warning(f"from get_embedding - unexpected empty string found in {prompts}")

        inputs = self.tokenizer(filtered_prompts, return_tensors='pt', padding=True)
        inputs = {k:v.to(self.model.device) for k, v in inputs.items()}
        attention_mask = inputs['attention_mask']

        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)

            last_hidden = outputs['hidden_states'][-1]
            attention_mask = attention_mask.unsqueeze(-1)
            masked_hidden = last_hidden * attention_mask
            embeddings = torch.sum(masked_hidden,dim=1)
            n_tokens = torch.sum(attention_mask,dim=1)
            embeddings = embeddings / n_tokens

        return [e.tolist() for e in embeddings]
    
    def get_contexted_embedding(self, prompts):
        prompt_len = [len(prompt) for prompt in prompts]
        concatenated_prompt = "\n".join(prompts)
        token_pos_per_prompt = [[0,0] for _ in prompts]

        inputs = self.tokenizer(
            concatenated_prompt, 
            return_tensors='pt',
            return_offsets_mapping=True)
        inputs = {k:v.to(self.model.device) for k,v in inputs.items()}

        
        p_i = 0 # prompt idx
        p_1 = prompt_len[p_i] # end of prompt in concatenated prompt
        for i, (i0, _) in enumerate(inputs['offset_mapping'][0]):
            # token is from after this prompt
            if i0 >= p_1:
                # move left until the matching prompt is found
                while i0 >= p_1:
                    p_i += 1
                    p_1 += prompt_len[p_i] + 1 # 1 is for "\n"
                token_pos_per_prompt[p_i][0] = i # position of the first token of the prompt
                token_pos_per_prompt[p_i][1] = i # position after the last token of the prompt
            token_pos_per_prompt[p_i][1] += 1

        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)

        last_hidden = outputs['hidden_states'][-1][0]

        # per-prompt average pool
        embeddings = []
        for t0, t1 in token_pos_per_prompt:
            if t1-t0 > 0:
                embedding = torch.mean(last_hidden[t0:t1],dim=0).tolist()
            else:
                embedding = None
            embeddings.append(embedding)

        return embeddings




# myEmbeddingLM = EmbeddingLM(
#     model_id = "Qwen/Qwen2-0.5B",
#     device='cpu'
# )