# coding: utf-8
import os, time, hashlib, base64, json, _thread as thread, requests
import torch
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import websocket
import ssl
from urllib.parse import urlparse
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
import hmac

load_dotenv()
APPID = os.getenv('XUNFEI_APPID')
API_KEY = os.getenv('XUNFEI_API_KEY')
SECRET = os.getenv('XUNFEI_API_SECRET')

# 检查环境变量是否配置
if not all([APPID, API_KEY, SECRET]):
    raise ValueError("请在.env文件中配置XUNFEI_APPID、XUNFEI_API_KEY、XUNFEI_API_SECRET")


class Ws_Param(object):
    def __init__(self, appid, api_key, api_secret, gpt_url):
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = urlparse(gpt_url).netloc
        self.path = urlparse(gpt_url).path
        self.gpt_url = gpt_url

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"
        signature_sha = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        v = {"authorization": authorization, "date": date, "host": self.host}
        return self.gpt_url + '?' + urlencode(v)


def get_answer(query, docs, history):
    # 存储API返回的结果
    result = {"content": "", "error": None}
    websocket_opened = False

    def on_message(ws, message):
        nonlocal websocket_opened
        try:
            data = json.loads(message)
            code = data['header']['code']
            if code != 0:
                result["error"] = f'API返回错误: {code}, 消息: {data.get("header", {}).get("message", "未知错误")}'
                print(f"❌ API错误: {result['error']}")
                ws.close()
            else:
                choices = data["payload"]["choices"]
                status = choices["status"]
                content = choices["text"][0]["content"]
                result["content"] += content
                print(f"📝 收到回答片段: {content[:50]}...")  # 调试信息
                if status == 2:
                    ws.close()
        except Exception as e:
            result["error"] = f"处理WebSocket消息失败: {str(e)}"
            print(f"❌ 消息处理错误: {result['error']}")
            ws.close()

    def on_error(ws, error):
        result["error"] = f"WebSocket连接错误: {str(error)}"
        print(f"❌ WebSocket错误: {result['error']}")

    def on_close(ws, close_status_code, close_msg):
        print(f"🔚 WebSocket连接关闭: 状态码={close_status_code}, 消息={close_msg}")

    def on_open(ws):
        nonlocal websocket_opened
        websocket_opened = True
        print("✅ WebSocket连接已建立，发送请求...")

        def run(*args):
            try:
                # 处理知识库内容
                ctx = '\n'.join([d.get('document', '') for d in docs]) if docs else "无相关知识"
                print(f"📚 知识库内容长度: {len(ctx)} 字符")

                # 构建消息列表 - 简化格式
                msgs = [
                    {
                        "role": "user",
                        "content": f"请你以中医的身份回答用户的问题，可酌情加入“根据资料”“参考信息”等提示，"
                                   f"但无需指出具体来源，请你按照多个方面回答问题：知识如下：{ctx}；用户问题：{query}"
                    }
                ]

                # 如果有历史记录，添加到消息中
                if history and len(history) > 0:
                    print(f"📖 使用历史记录: {len(history)} 条")
                    # 将历史记录转换为API格式
                    for msg in history[-6:]:  # 只使用最近6条历史记录
                        if isinstance(msg, dict):
                            if 'user' in msg and 'assistant' in msg:
                                msgs.insert(-1, {"role": "user", "content": msg['user']})
                                msgs.insert(-1, {"role": "assistant", "content": msg['assistant']})

                # 生成请求数据
                data = {
                    "header": {
                        "app_id": APPID,
                        "uid": "user123"
                    },
                    "parameter": {
                        "chat": {
                            "domain": "lite",
                            "temperature": 0.5,
                            "max_tokens": 2048
                        }
                    },
                    "payload": {
                        "message": {
                            "text": msgs
                        }
                    }
                }

                print(f"📤 发送请求数据，消息数: {len(msgs)}")
                ws.send(json.dumps(data))
                print("✅ 请求已发送")

            except Exception as e:
                result["error"] = f"构建请求数据失败: {str(e)}"
                print(f"❌ 请求构建错误: {result['error']}")
                ws.close()

        thread.start_new_thread(run, ())

    try:
        # 配置WebSocket连接参数
        Spark_url = "wss://spark-api.xf-yun.com/v1.1/chat"
        ws_param = Ws_Param(APPID, API_KEY, SECRET, Spark_url)
        ws_url = ws_param.create_url()
        websocket.enableTrace(False)

        print(f"🔗 连接URL: {ws_url.split('?')[0]}...")  # 不打印完整URL避免泄露密钥

        # 建立WebSocket连接
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        # 设置超时
        ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE},
            ping_timeout=30,
            ping_interval=35
        )

        # 检查连接是否成功建立
        if not websocket_opened:
            result["error"] = "WebSocket连接未能建立"

    except Exception as e:
        result["error"] = f"WebSocket初始化失败: {str(e)}"
        print(f"❌ WebSocket初始化错误: {result['error']}")

    # 返回结果
    if result["error"]:
        print(f"❌ 最终错误: {result['error']}")
        return f"抱歉，暂时无法回答问题。错误: {result['error']}"

    if result["content"]:
        print(f"✅ 回答生成成功，长度: {len(result['content'])} 字符")
        return result["content"]
    else:
        print("⚠️ 未获取到有效回答")
        return "抱歉，暂时无法生成回答，请稍后重试。"


# ---------- 2. 免费 embedding（GPU加速版） ----------
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        print(f"✅ GPU加速已启用（设备：{torch.cuda.get_device_name(0)}）")
    else:
        print("⚠️ 未检测到可用GPU，将使用CPU运行")

    local_model = SentenceTransformer(
        model_name_or_path=r'C:\Users\21316\Desktop\Small_project_code\moudle_ifly\mod',
        device=device
    )
except Exception as e:
    raise RuntimeError(f"本地模型加载失败：{str(e)}")


def get_embedding(texts):
    try:
        single_input = False
        if isinstance(texts, str):
            texts = [texts.strip()]
            single_input = True
        else:
            texts = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
            single_input = False

        if not texts:
            return [] if not single_input else []

        embeddings = local_model.encode(
            sentences=texts,
            normalize_embeddings=True,
            batch_size=32
        )

        result = embeddings.tolist()

        if single_input and result:
            return result[0]
        else:
            return result

    except Exception as e:
        print(f"Embedding生成失败：{str(e)}")
        return [] if not single_input else []


# ---------- 3. 免费语音合成（xiaoyan 音色） ----------
def tts_free(text: str, save_path: str = "reply.wav"):
    try:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("合成文本不能为空")

        t = str(int(time.time()))
        sig = hashlib.md5((API_KEY + t + APPID).encode()).hexdigest()
        headers = {
            "X-Appid": APPID,
            "X-CurTime": t,
            "X-Param": base64.b64encode(b'{"voice_name":"xiaoyan","engine":"intp65","aue":"raw"}').decode(),
            "X-Sign": sig,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {"text": text.strip()}
        resp = requests.post(
            "https://tts-api.xf-yun.com/v2/tts",
            data=data,
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        result = resp.json()

        if "code" in result and result["code"] != 0:
            raise RuntimeError(f"TTS接口错误（{result['code']}）：{result.get('message', '未知错误')}")

        if "data" in result and "audio" in result["data"]:
            audio_b64 = result["data"]["audio"]
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            return save_path
        else:
            raise KeyError("TTS响应中缺少data.audio字段")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"TTS网络请求失败：{str(e)}")
    except Exception as e:
        raise RuntimeError(f"TTS合成失败：{str(e)}")