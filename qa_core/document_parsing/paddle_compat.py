"""针对固定 PaddleX 3.3.10 工作进程的局部兼容处理。

修复仅作用于受控的模型构建或对象引用；不得扩展为全局依赖升级或永久猴子补丁。"""
from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def skip_disabled_chart_model(pipeline_type=None):
    """在禁用图表识别时避免预加载 PP-Chart2Table。

    PaddleX 3.3.10 会无条件构造该可选模型；兼容处理仅限单线程隔离工作进程
    内的引擎构建期间，结束即恢复原类。其他模型及显式启用的图表识别保留原行为。"""
    if pipeline_type is None:
        from paddlex.inference.pipelines.layout_parsing.pipeline_v2 import _LayoutParsingPipelineV2
        pipeline_type = _LayoutParsingPipelineV2
    original = pipeline_type.create_model
    owned = pipeline_type.__dict__.get("create_model")

    def create_model(instance, config, **kwargs):
        if (getattr(instance, "use_chart_recognition", True) is False
                and config.get("model_name") == "PP-Chart2Table"):
            return None
        return original(instance, config, **kwargs)

    pipeline_type.create_model = create_model
    try:
        yield
    finally:
        if owned is None:
            del pipeline_type.create_model
        else:
            pipeline_type.create_model = owned


def share_table_ocr_pipeline(engine):
    """让表格拆分单元格分支复用父级 OCR 识别器，避免重复加载本地模型。

    PaddleX 3.3.10 的 PP-Structure 禁用了表格局部 OCR 初始化，但拆分单元格
    仍需 text_rec_model；这里复用已有父流水线，不另建第二套模型。"""
    layout = engine.paddlex_pipeline
    if layout.use_table_recognition:
        table = layout.table_recognition_pipeline._pipeline
        if table.general_ocr_pipeline is None:
            table.general_ocr_pipeline = layout.general_ocr_pipeline
    return engine
