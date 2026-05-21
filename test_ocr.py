# test_ocr_final.py（简化版，跳过错误的语言包检查，直接调用OCR）
import pytesseract
from PIL import Image
import os

# 1. 配置Tesseract核心路径（与命令行一致，D盘正确路径）
pytesseract.pytesseract_cmd = r"D:\ocr\tesseract.exe"
os.environ['TESSDATA_PREFIX'] = r"D:\ocr"  # 指向tessdata的父目录（必须正确）

# 2. 测试图片路径（确保图片存在，建议用简单路径）
img_path = r"C:\Users\21316\Pictures\Screenshots\屏幕截图 2025-09-16 222542.png"

try:
    # 验证图片是否能正常打开
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"图片不存在！路径：{img_path}")
    img = Image.open(img_path)
    print(f"✅ 图片加载成功！尺寸：{img.size}")

    # 3. 直接调用OCR（用命令行已验证的语言包：chi_sim+eng）
    text = pytesseract.image_to_string(
        image=img,
        lang="chi_sim+eng",  # 命令行已证明这两个语言包存在
        config=r"--tessdata-dir D:/ocr/tessdata"  # 路径与环境一致
    )

    # 输出结果
    print("\n🎉 OCR识别成功！提取的文字：")
    print("=" * 60)
    print(text if text.strip() else "⚠️  识别到空文本（可能图片文字不清晰）")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 错误详情：")
    print(f"错误类型：{type(e).__name__}")
    print(f"错误信息：{str(e)}")