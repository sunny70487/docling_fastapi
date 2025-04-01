from typing import Optional, Dict, List, Literal
from pydantic import BaseModel

from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    EasyOcrOptions,
    PdfBackend,
    PdfPipeline,
    TableFormerMode,
    VlmModelType,
)
from docling_core.types.doc import ImageRefMode

class ConversionRequest(BaseModel):
    source: str
    output_filename: Optional[str] = None
    format: Literal["markdown", "json", "yaml", "html", "text", "doctags"] = "markdown"
    image_export_mode: ImageRefMode = ImageRefMode.REFERENCED
    pipeline: PdfPipeline = PdfPipeline.STANDARD
    vlm_model: VlmModelType = VlmModelType.SMOLDOCLING
    ocr: bool = True
    force_ocr: bool = False
    ocr_engine: str = EasyOcrOptions.kind
    ocr_lang: Optional[str] = None
    pdf_backend: PdfBackend = PdfBackend.DLPARSE_V2
    table_mode: TableFormerMode = TableFormerMode.ACCURATE
    enrich_code: bool = False
    enrich_formula: bool = False
    enrich_picture_classes: bool = False
    enrich_picture_description: bool = False
    num_threads: int = 4
    device: AcceleratorDevice = AcceleratorDevice.AUTO

class ProgressInfo(BaseModel):
    task_id: str
    progress: int
    status: str
    message: str

class DocumentInfo(BaseModel):
    filename: str
    created: float
    size: int
    format: str

class ConversionOptions(BaseModel):
    """文件轉換選項"""
    image_export_mode: ImageRefMode = ImageRefMode.REFERENCED
    pipeline: PdfPipeline = PdfPipeline.STANDARD
    vlm_model: VlmModelType = VlmModelType.SMOLDOCLING
    ocr: bool = True
    force_ocr: bool = False
    ocr_engine: str = EasyOcrOptions.kind
    ocr_lang: Optional[str] = None
    pdf_backend: PdfBackend = PdfBackend.DLPARSE_V2
    table_mode: TableFormerMode = TableFormerMode.ACCURATE
    enrich_code: bool = False
    enrich_formula: bool = False
    enrich_picture_classes: bool = False
    enrich_picture_description: bool = False
    num_threads: int = 4
    device: AcceleratorDevice = AcceleratorDevice.AUTO
