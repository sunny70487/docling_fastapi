from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import importlib
import platform
import sys

from config import CONVERSION_PROGRESS, OUTPUT_DIR, ACTIVE_BATCH_TASKS # Import necessary config
from docling.models.factories import get_ocr_factory
from docling_core.types.doc import ImageRefMode
from docling.datamodel.pipeline_options import (
    PdfPipeline, VlmModelType, PdfBackend, TableFormerMode, AcceleratorDevice
)

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Access templates from app state
    templates = request.app.state.templates
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/progress/{task_id}")
async def get_progress(task_id: str):
    """取得轉換進度"""
    # 使用從 config 匯入的字典
    if task_id not in CONVERSION_PROGRESS:
        raise HTTPException(status_code=404, detail="找不到該任務")
    return CONVERSION_PROGRESS[task_id]

@router.get("/api/ocr-engines")
async def get_ocr_engines(allow_external_plugins: bool = False):
    """獲取系統中可用的 OCR 引擎"""
    ocr_factory = get_ocr_factory(allow_external_plugins=allow_external_plugins)
    engines = []
    for meta in ocr_factory.registered_meta.values():
        engines.append({
            "name": meta.kind,
            "plugin": meta.plugin_name,
            "package": meta.module.split(".")[0],
            "is_external": not meta.module.startswith("docling.")
        })
    return {"engines": engines}

@router.get("/api/conversion-options")
async def get_conversion_options():
    """獲取可用的轉換選項"""
    return {
        "image_export_modes": [mode.value for mode in ImageRefMode],
        "pipelines": [pipeline.value for pipeline in PdfPipeline],
        "vlm_models": [model.value for model in VlmModelType],
        "pdf_backends": [backend.value for backend in PdfBackend],
        "table_modes": [mode.value for mode in TableFormerMode],
        "accelerator_devices": [device.value for device in AcceleratorDevice]
    }

@router.get("/version")
async def get_version():
    """獲取 Docling 版本資訊"""
    try:
        docling_version = importlib.metadata.version("docling")
        docling_core_version = importlib.metadata.version("docling-core")
        # Handle potential missing optional packages gracefully
        try:
            docling_ibm_models_version = importlib.metadata.version("docling-ibm-models")
        except importlib.metadata.PackageNotFoundError:
            docling_ibm_models_version = "Not Installed"
        try:
            docling_parse_version = importlib.metadata.version("docling-parse")
        except importlib.metadata.PackageNotFoundError:
            docling_parse_version = "Not Installed"
            
        platform_str = platform.platform()
        py_impl_version = sys.implementation.cache_tag
        py_lang_version = platform.python_version()
        
        return {
            "docling": docling_version,
            "docling_core": docling_core_version,
            "docling_ibm_models": docling_ibm_models_version,
            "docling_parse": docling_parse_version,
            "python": f"{py_impl_version} ({py_lang_version})",
            "platform": platform_str
        }
    except Exception as e:
        print(f"獲取版本資訊時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"獲取版本資訊失敗: {str(e)}")

@router.get("/output/{filename}")
async def download_output(filename: str):
    """下載已轉換的輸出檔案"""
    # 使用從 config 匯入的路徑
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="找不到檔案")
    
    return FileResponse(
        path=file_path, 
        filename=filename,
        media_type="application/octet-stream" # 通用二進位流
    )

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_management_page(request: Request):
    """任務管理頁面"""
    # Access templates from app state
    templates = request.app.state.templates
    return templates.TemplateResponse("tasks.html", {"request": request})

@router.get("/batch-convert", response_class=HTMLResponse)
async def batch_convert_page(request: Request):
    """批量轉換頁面"""
    # Use shared templates from app state
    templates = request.app.state.templates
    return templates.TemplateResponse("batch_convert.html", {"request": request})
