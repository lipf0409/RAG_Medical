import os, chromadb, PyPDF2, hashlib, pytesseract, docx
from PIL import Image
from pdf2image import convert_from_path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from ifly import get_embedding
import io

# --------------------------
# 核心修改：同步Tesseract路径为D盘实际安装目录（D:\ocr）
# --------------------------
# 1. 强制设置TESSDATA_PREFIX（指向tessdata的父目录，而非tessdata本身）
os.environ['TESSDATA_PREFIX'] = r"D:\ocr"
# 2. 显式指定tesseract.exe路径（与命令行验证的路径一致）
pytesseract.pytesseract_cmd = r"D:\ocr\tesseract.exe"

# --------------------------
# Chroma数据库配置（保持不变）
# --------------------------
CHROMA_PATH = os.getenv('CHROMA_PATH', './chroma_db')  # 默认路径，避免未配置时出错
client = chromadb.PersistentClient(path=CHROMA_PATH)
col = client.get_or_create_collection(name='lan')


# --------------------------
# OCR通用函数（核心修改：添加config参数，确保语言包正确加载）
# --------------------------
def ocr_image(img: Image.Image) -> str:
    try:
        # 显式指定tessdata目录，避免依赖环境变量解析，路径无空格无需额外引号
        config = r"--tessdata-dir D:/ocr/tessdata"
        return pytesseract.image_to_string(
            img,
            lang='chi_sim+eng',  # 中文+英文识别（命令行已验证语言包存在）
            config=config
        ).strip()
    except Exception as e:
        # 详细打印OCR错误，方便排查（如图片损坏、路径异常）
        print(f'OCR识别失败：{str(e)}')
        return ''


# --------------------------
# Word内嵌图片处理（保持不变，进度提示保留）
# --------------------------
def word2text_with_ocr(path: str) -> str:
    doc = docx.Document(path)
    full_text = [p.text for p in doc.paragraphs]
    img_count = 0  # 统计图片数量，用于进度提示
    for rel in doc.part.rels.values():
        if 'image' in rel.target_ref:
            img_count += 1
            try:
                print(f'  正在识别Word中的第{img_count}张图片...')  # 进度可视化
                img_bytes = rel.target_part.blob
                img = Image.open(io.BytesIO(img_bytes))
                ocr_text = ocr_image(img)
                full_text.append(ocr_text)  # OCR结果追加到文本中
            except Exception as e:
                print(f'OCR skip image in {path}: {e}')
    return '\n'.join(full_text)


# --------------------------
# PDF文本+OCR处理（优化：补充进度提示，保留异常捕获）
# --------------------------
def pdf2text_with_ocr(path: str) -> str:
    text = ''
    # 1. 提取PDF原生文本（非扫描页）
    print('  正在提取PDF原生文本...')
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        total_pages = len(reader.pages)
        for i, p in enumerate(reader.pages, 1):
            text += (p.extract_text() or '')  # 空页跳过
            # 每10页打印一次进度，避免频繁输出
            if i % 10 == 0 or i == total_pages:
                print(f'  已提取PDF第{i}/{total_pages}页原生文本')

    # 2. 扫描页转图片+OCR（补充原生文本无法提取的内容）
    try:
        print('  正在处理PDF扫描页（转图片+OCR）...')
        # 注意：需确保POPPLER已安装并配置环境变量，若报错需手动指定路径（如 poppler_path=r"D:\poppler-24.02.0\Library\bin"）
        images = convert_from_path(
            path,
            dpi=200,  # 分辨率适中，平衡识别精度和速度
            fmt='png',
            thread_count=2,  # 多线程加速图片转换
            poppler_path=os.getenv('POPPLER_PATH')
        )
        total_images = len(images)
        for i, img in enumerate(images, 1):
            ocr_text = ocr_image(img)
            text += '\n' + ocr_text  # OCR结果追加到总文本
            # 每5页打印一次OCR进度
            if i % 5 == 0 or i == total_images:
                print(f'  已OCR处理PDF第{i}/{total_images}页扫描页')
    except Exception as e:
        # 若POPPLER未配置，仅提示不中断（原生文本仍可提取）
        print(f'  扫描页处理跳过：{e}（需安装POPPLER并配置POPPLER_PATH环境变量）')
    return text


# --------------------------
# 文件文本提取统一入口（保持不变）
# --------------------------
def file2text(path: str) -> str:
    path_lower = path.lower()
    if path_lower.endswith('.pdf'):
        return pdf2text_with_ocr(path)
    elif path_lower.endswith('.docx'):
        return word2text_with_ocr(path)
    else:
        return ''


# --------------------------
# 灌库逻辑（已验证：重复ID解决方案保留，进度输出保留）
# --------------------------
def ingest_dir(dir_path):
    # 1. 筛选待处理文件（仅PDF和DOCX）
    valid_extensions = ('.pdf', '.docx')
    all_files = [
        fn for fn in os.listdir(dir_path)
        if fn.lower().endswith(valid_extensions) and os.path.isfile(os.path.join(dir_path, fn))
    ]
    total_files = len(all_files)
    if total_files == 0:
        print(f'⚠️  目录 {dir_path} 中未找到PDF或DOCX文件，无需处理')
        return

    # 文本分割配置（chunk大小300，重叠50，平衡语义完整性和检索精度）
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)

    # 2. 遍历处理每个文件，带进度提示
    for current_idx, fn in enumerate(all_files, 1):
        full_path = os.path.join(dir_path, fn)
        progress = f'[{current_idx}/{total_files} ({int(current_idx / total_files * 100)}%)]'
        print(f'\n{progress} 开始处理文件：{fn}')

        # 3. 提取文件文本（原生文本+OCR）
        print(f'{progress} 正在提取文本（含OCR）...')
        text = file2text(full_path)
        if not text.strip():
            print(f'{progress} ⚠️  未提取到有效文本，已跳过该文件')
            continue

        # 4. 文本分割为chunk
        chunks = splitter.split_text(text)
        print(f'{progress} 正在分割文本（共生成{len(chunks)}个chunk）...')

        # 5. GPU加速生成嵌入向量（已在ifly.py中配置GPU）
        print(f'{progress} 正在生成嵌入向量（GPU加速中...）...')
        embeddings = get_embedding(chunks)  # 批量生成，效率更高

        # 6. 生成绝对唯一的ID（文件序号+文件名+chunk索引+文本，避免重复）
        ids = [
            hashlib.md5(
                (f"{current_idx}_{fn}_{i}_{c}").encode()
            ).hexdigest()
            for i, c in enumerate(chunks)
        ]

        # 7. 入库（Chroma）
        print(f'{progress} 正在入库（{len(chunks)}个chunk）...')
        col.add(ids=ids, documents=chunks, embeddings=embeddings)

        # 8. 单个文件处理完成
        print(f'{progress} ✅ 处理完成！{fn} 已入库 {len(chunks)} 个chunk')

    # 所有文件处理完成
    print(f'\n📊 灌库任务结束！共处理 {total_files} 个文件，累计入库chunk数可通过Chroma查询')


# --------------------------
# 检索函数（修复：确保嵌入向量格式正确）
# --------------------------
def retrieve_topk(query, top_k=3):
    emb = get_embedding(query)

    # 调试信息
    print(f"查询: '{query}'")
    print(f"嵌入向量类型: {type(emb)}, 长度: {len(emb) if hasattr(emb, '__len__') else 'N/A'}")

    if not emb:
        print("⚠️ 嵌入向量生成失败，返回空结果")
        return []

    # 确保嵌入向量是二维格式
    if isinstance(emb[0], list):
        # 已经是二维（批量查询的情况）
        query_embedding = emb
    else:
        # 一维转二维（单个查询）
        query_embedding = [emb]

    try:
        res = col.query(query_embeddings=query_embedding, n_results=top_k)
        print(f"✅ 检索到 {len(res['documents'][0])} 个相关文档")
        return [{'document': d, 'distance': res['distances'][0][i]} for i, d in enumerate(res['documents'][0])]
    except Exception as e:
        print(f"❌ ChromaDB查询失败: {str(e)}")
        return []