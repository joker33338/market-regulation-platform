"""Local document parsing. Importing this package never loads inference models."""
from .config import ParsingConfig
from .schemas import DocumentResult, PageResult

__all__ = ["ParsingConfig", "DocumentResult", "PageResult"]

