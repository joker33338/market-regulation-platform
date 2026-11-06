# 离线模型

本目录中的 bge-m3 从现有 KnowForge 项目复制，校验结果见 models/model_manifest.json。
默认 Embedding 使用本地 CPU 模型，不需要远程模型服务。
目录和模型文件不应提交到 Git；保留模型自带说明和许可证信息。

本 MVP 不使用意图分类器、reranker 或生成式大模型，因此未复制这些额外模型。
OCR 是可选功能，要求提供已下载的 PaddleOCR 检测、识别和方向分类模型目录。

