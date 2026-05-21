# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_restful import Api, Resource
from flask_cors import CORS
from dotenv import load_dotenv
import os
import redis
import json
import hashlib
import traceback
import time
import logging          # ← 新增：日志模块

from knowledge import ingest_dir, retrieve_topk
from ifly import get_answer

# ---------------- 基础配置 ----------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("app")

# ---------------- Flask 实例 ----------------
# 明确指定 static 文件夹，避免部署时路径歧义
app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app, resources={r"/api/*": {"origins": "*"}})
api = Api(app)

# ---------------- Redis 连接 ----------------
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_db   = int(os.getenv("REDIS_DB", 0))

try:
    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=True,
        socket_timeout=5
    )
    r.ping()
    logger.info("✅ Redis 连接成功")
except Exception as e:
    logger.error(f"❌ Redis 连接失败：{e}")
    # 开发阶段可继续运行，生产环境建议 exit(1)
    # exit(1)

# ---------------- 全局异常处理 ----------------
@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    logger.error(f"未捕获异常：{e}")
    return jsonify(code=500, msg="Internal Server Error", detail=str(e)), 500

# ---------------- 兜底 404 → 204（可选） ----------------
@app.errorhandler(404)
def not_found(e):
    # 对浏览器自动探针返回空，避免 404 污染日志
    return "", 204

# ---------------- 浏览器探针路由 ----------------
@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools():
    return "", 204

# ---------------- 前端首页 ----------------
@app.route("/")
def index():
    return app.send_static_file("index.html")

# ---------------- 业务资源：QA ----------------
class QA(Resource):
    def post(self):
        try:
            if not request.is_json:
                return jsonify(code=415, msg="Unsupported Media Type", detail="Request must be JSON"), 415

            data = request.get_json() or {}
            uid = data.get("user_id", "").strip()
            q = data.get("query", "").strip()

            if not uid or not q:
                return jsonify(code=400, msg="缺参数", detail="user_id 和 query 为必传参数")

            # history 逻辑
            if "history" in data:
                hist = data["history"]
                if not isinstance(hist, list):
                    hist = []
            else:
                redis_hist = r.get(f"s:{uid}") or "[]"
                try:
                    hist = json.loads(redis_hist)
                except json.JSONDecodeError:
                    hist = []
                if not isinstance(hist, list):
                    hist = []

            logger.info(f"📥 接收请求：user_id={uid}, query={q}, history 长度={len(hist)}")
            docs = retrieve_topk(q, top_k=3)
            if not isinstance(docs, list):
                docs = []
                logger.warning("retrieve_topk 返回非列表，已重置为空列表")

            ans = get_answer(q, docs, hist)
            ans = ans.strip() or "抱歉，暂时无法回答你的问题"

            hist.append({"user": q, "assistant": ans, "timestamp": int(time.time())})
            r.setex(f"s:{uid}", 3600, json.dumps(hist, ensure_ascii=False))

            return jsonify(code=200, msg="success", data={"answer": ans, "history": hist})

        except Exception as e:
            logger.exception("处理请求失败")
            return jsonify(code=500, msg="处理请求失败", detail=str(e)), 500
# ---------------- 注册 API ----------------
api.add_resource(QA, "/api/qa")


# ---------------- 启动 ----------------
if __name__ == "__main__":
    flask_host = os.getenv("FLASK_HOST", "0.0.0.0")
    flask_port = int(os.getenv("FLASK_PORT", 8000))
    # 生产环境请使用 uwsgi / gunicorn，debug=False
    app.run(host=flask_host, port=flask_port, debug=False)