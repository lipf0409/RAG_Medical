# RAG_Medical

基于RAG的索引增强自建知识库的后端

## 项目简介

本项目实现了一个完整的知识库问答流程：

1. 文档处理：支持 PDF、DOCX 文件的文本提取与 OCR 识别
2. 向量存储：使用 ChromaDB 存储文档嵌入向量
3. 语义检索：基于本地 SentenceTransformer 模型进行相似度检索
4. 智能问答：通过讯飞星火大模型生成专业回答
5. Web 服务：Flask 后端 + 前端聊天界面

## 技术栈

- 后端框架: Flask + Flask-RESTful
- 向量数据库: ChromaDB
- 嵌入模型: SentenceTransformer (本地部署，支持 GPU 加速)
- 大模型 API: 讯飞星火 Lite 版
- OCR 工具: Tesseract (中文 + 英文)
- PDF 处理: PyPDF2 + pdf2image (需 Poppler)
- 缓存: Redis (会话历史存储)

## 目录结构

moudle_ifly/
 app.py              # Flask 主应用，API 服务入口
 ifly.py             # 讯飞 API 封装：问答、嵌入、语音合成
 knowledge.py        # 知识库管理：文档解析、向量入库、检索
 cli.py              # 命令行工具：知识库灌库入口
 static/
    index.html      # 前端聊天界面
 data/               # 知识库文档目录 (PDF/DOCX)
 mod/                # 本地嵌入模型 (需单独下载)
 chroma_data/        # ChromaDB 数据存储 (可重新生成)
 .env                # 环境变量配置 (不提交)
 .gitignore
 requirements.txt    # Python 依赖
 README.md

## 环境要求

- Python 3.8+
- Redis (可选，用于会话历史)
- Tesseract OCR (处理扫描文档)
- Poppler (PDF 转图片)
- CUDA 环境 (可选，GPU 加速嵌入计算)

## 安装步骤

### 1. 克隆项目

git clone https://github.com/lipf0409/RAG_Medical.git
cd RAG_Medical

### 2. 安装依赖

pip install -r requirements.txt

### 3. 配置环境变量

创建 .env 文件：

# 讯飞 API 配置
XUNFEI_APPID=your_appid
XUNFEI_API_KEY=your_api_key
XUNFEI_API_SECRET=your_api_secret

# Redis 配置 (可选)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Flask 配置
FLASK_HOST=0.0.0.0
FLASK_PORT=8000

# ChromaDB 路径
CHROMA_PATH=./chroma_db

# OCR 配置 (Windows)
TESSDATA_PREFIX=D:/ocr
POPPLER_PATH=D:/poppler/Library/bin

### 4. 下载嵌入模型

从 HuggingFace 下载中文 SentenceTransformer 模型，放置到 mod/ 目录。
推荐模型：shibing624/text2vec-base-chinese

### 5. 准备知识库文档

将 PDF 或 DOCX 文档放入 data/ 目录。

### 6. 构建向量索引

python cli.py --dir ./data

### 7. 启动服务

python app.py

访问 http://localhost:8000 使用聊天界面。

## API 接口

### POST /api/qa

问答接口

请求体:
{
  "user_id": "user123",
  "query": "高血压患者如何调理饮食?",
  "history": []
}

响应:
{
  "code": 200,
  "msg": "success",
  "data": {
    "answer": "根据资料...",
    "history": [{"user": "...", "assistant": "...", "timestamp": 1234567890}]
  }
}

## 注意事项

1. .env 文件包含敏感信息，请勿提交到 Git
2. mod/ 目录体积较大 (约 800MB)，建议单独下载或使用 Git LFS
3. data/ 目录中的文档为示例数据，可根据实际需求替换
4. 生产环境建议使用 Gunicorn 或 uWSGI 部署

## 许可证

MIT License
