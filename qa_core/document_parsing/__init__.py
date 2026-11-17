"""文档解析包入口。

导入包本身不加载推理模型；具体模型由调用链按需初始化。原生抽取、OCR 和
版面结构解析共用结果协议，但识别完成不代表审核或发布完成。"""
from .config import ParsingConfig
from .schemas import DocumentResult, PageResult

__all__ = ["ParsingConfig", "DocumentResult", "PageResult"]

