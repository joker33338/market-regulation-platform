"""Scoped compatibility fixes for the pinned PaddleX 3.3.10 worker."""
from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def skip_disabled_chart_model(pipeline_type=None):
    """Avoid eagerly loading PP-Chart2Table when chart recognition is disabled.

    PaddleX 3.3.10 constructs this optional model unconditionally. Restrict the
    workaround to engine construction in our single-threaded isolated worker,
    and restore the original class immediately afterwards. Other models and
    explicitly enabled chart recognition retain the original behavior.
    """
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
    """Reuse the existing recognizer for PaddleX's split-cell OCR branch.

    In 3.3.10 PP-Structure disables table-local OCR initialization, but split
    cells still require text_rec_model. Reuse the parent OCR pipeline instead
    of loading a second copy of the same local models.
    """
    layout = engine.paddlex_pipeline
    if layout.use_table_recognition:
        table = layout.table_recognition_pipeline._pipeline
        if table.general_ocr_pipeline is None:
            table.general_ocr_pipeline = layout.general_ocr_pipeline
    return engine
