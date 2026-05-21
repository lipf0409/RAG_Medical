import argparse, os
from knowledge import ingest_dir

# 增加启动提示
print('====== 开始知识库灌库流程 ======')

parser = argparse.ArgumentParser(description='知识库灌库工具：处理指定目录下的PDF和DOCX文件并入库')
parser.add_argument('--dir', required=True, help='待处理文档所在目录（例如 ./data）')
args = parser.parse_args()

# 验证目录是否存在
if not os.path.isdir(args.dir):
    print(f'❌  错误：目录 {args.dir} 不存在，请检查路径是否正确')
else:
    print(f'📂  目标目录：{args.dir}')
    ingest_dir(args.dir)
    print('\n====== 灌库完成！所有文件已处理 ======')