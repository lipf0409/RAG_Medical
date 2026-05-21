from sentence_transformers import SentenceTransformer

local_model_path = r"C:\Users\21316\Desktop\moudle_ifly\mod"          # 本地模型目录不变
model = SentenceTransformer(local_model_path, device='cuda')  # ← 只改这里

sentence = "这是一个测试句子"
embedding = model.encode(sentence)
print("句子向量维度：", embedding.shape)   # (768,)
print("设备:", model.device)             # 应输出 cuda:0