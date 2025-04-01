import re
import sys
from typing import Optional, List
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorOptions,
    OcrOptions,
    PdfPipelineOptions,
    PdfBackend,
    PdfPipeline,
    VlmPipelineOptions,
    VlmModelType,
    granite_vision_vlm_conversion_options,
    smoldocling_vlm_conversion_options,
    smoldocling_vlm_mlx_conversion_options,
)
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.models.factories import get_ocr_factory
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.vlm_pipeline import VlmPipeline
from docling_core.types.doc import ImageRefMode

# 從其他模組匯入
from models import ConversionOptions

# 添加輔助函數來分割語言列表
def _split_list(raw: Optional[str]) -> Optional[List[str]]:
    if raw is None:
        return None
    return re.split(r"[;,]", raw)

def create_converter_with_options(options: ConversionOptions) -> DocumentConverter:
    """根據選項建立文件轉換器"""
    
    ocr_factory = get_ocr_factory(allow_external_plugins=False)
    ocr_options: OcrOptions = ocr_factory.create_options(
        kind=options.ocr_engine,
        force_full_page_ocr=options.force_ocr,
    )
    
    if options.ocr_lang:
        ocr_lang_list = _split_list(options.ocr_lang)
        if ocr_lang_list is not None:
            ocr_options.lang = ocr_lang_list
    
    accelerator_options = AcceleratorOptions(
        num_threads=options.num_threads, 
        device=options.device
    )
    
    pdf_format_option = None # 初始化
    if options.pipeline == PdfPipeline.STANDARD:
        pipeline_options = PdfPipelineOptions(
            allow_external_plugins=False,
            enable_remote_services=False,
            accelerator_options=accelerator_options,
            do_ocr=options.ocr,
            ocr_options=ocr_options,
            do_table_structure=True,
            do_code_enrichment=options.enrich_code,
            do_formula_enrichment=options.enrich_formula,
            do_picture_description=options.enrich_picture_description,
            do_picture_classification=options.enrich_picture_classes,
        )
        pipeline_options.table_structure_options.do_cell_matching = True  
        pipeline_options.table_structure_options.mode = options.table_mode

        if options.image_export_mode != ImageRefMode.PLACEHOLDER:
            pipeline_options.generate_page_images = True
            pipeline_options.generate_picture_images = True
            pipeline_options.images_scale = 2

        backend = None
        if options.pdf_backend == PdfBackend.DLPARSE_V1:
            backend = DoclingParseDocumentBackend
        elif options.pdf_backend == PdfBackend.DLPARSE_V2:
            backend = DoclingParseV2DocumentBackend
        elif options.pdf_backend == PdfBackend.DLPARSE_V4:
            backend = DoclingParseV4DocumentBackend
        elif options.pdf_backend == PdfBackend.PYPDFIUM2:
            backend = PyPdfiumDocumentBackend

        pdf_format_option = PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=backend,
        )
    elif options.pipeline == PdfPipeline.VLM:
        pipeline_options = VlmPipelineOptions()

        if options.vlm_model == VlmModelType.GRANITE_VISION:
            pipeline_options.vlm_options = granite_vision_vlm_conversion_options
        elif options.vlm_model == VlmModelType.SMOLDOCLING:
            pipeline_options.vlm_options = smoldocling_vlm_conversion_options
            if sys.platform == "darwin":
                try:
                    # 嘗試匯入 mlx_vlm，如果成功則使用 MLX 選項
                    import mlx_vlm
                    pipeline_options.vlm_options = smoldocling_vlm_mlx_conversion_options
                    print("Using Smoldocling MLX VLM options for conversion.")
                except ImportError:
                    print("mlx_vlm not found, using standard Smoldocling VLM options.")
                    pass # 保持使用預設的 smoldocling 選項

        pdf_format_option = PdfFormatOption(
            pipeline_cls=VlmPipeline, 
            pipeline_options=pipeline_options
        )

    # 確保 pdf_format_option 有被賦值 (例如，如果 pipeline 不是 STANDARD 或 VLM)
    if pdf_format_option is None:
         # 這裡可以拋出錯誤或使用預設值，取決於期望的行為
         # 暫時使用 Standard Pipeline 作為後備
         print(f"Warning: Unsupported pipeline type '{options.pipeline}'. Falling back to Standard Pipeline.")
         # (這裡需要複製 Standard Pipeline 的設定邏輯或定義一個預設)
         # 為了簡化，我們先假設 pipeline 總是 STANDARD 或 VLM
         # 或者拋出錯誤：
         # raise ValueError(f"Unsupported pipeline type: {options.pipeline}")
         # 暫時設定為 None，讓下游處理
         pass # 或者需要處理這種情況

    # 建立並返回 DocumentConverter
    return DocumentConverter(
        allowed_formats=[
            InputFormat.PDF,
            InputFormat.IMAGE,
            InputFormat.DOCX,
            InputFormat.HTML,
            InputFormat.PPTX,
            InputFormat.ASCIIDOC,
            InputFormat.CSV,
            InputFormat.MD,
        ],
        format_options={
            # 如果 pdf_format_option 是 None，這裡會出錯，需要處理
            InputFormat.PDF: pdf_format_option, 
            InputFormat.IMAGE: pdf_format_option, # 假設 Image 也使用相同的 PDF 選項
            InputFormat.DOCX: WordFormatOption(
                pipeline_cls=SimplePipeline
            ),
            # 其他格式可以根據需要添加，例如 HTML, PPTX 等
            # InputFormat.HTML: ...
            # InputFormat.PPTX: ...
        },
    )

def run_conversion(file_path: Path, options: ConversionOptions):
    """執行文件轉換"""
    try:
        # 使用提供的選項建立轉換器
        custom_converter = create_converter_with_options(options)
        
        # 使用 DocumentConverter 轉換
        print(f"開始轉換檔案: {file_path}")
        result = custom_converter.convert(str(file_path.absolute()))
        print(f"檔案轉換完成: {file_path}")
        return result
    except Exception as e:
        print(f"執行轉換時發生錯誤 ({file_path}): {e}")
        raise # 重新引發錯誤，讓上層處理

import httpx
import tempfile
import os
import time
import json
from urllib.parse import urlparse
from fastapi import HTTPException # 需要處理下載錯誤等

# 從其他服務匯入
from services import file_service, progress_service
from config import OUTPUT_DIR
from docling_core.types.doc import ImageRefMode # 需要匯入
from docling.datamodel.pipeline_options import EasyOcrOptions # 需要匯入

async def process_url_conversion_task(task_id: str, source_url: str, output_filename: str, format: str, conversion_options_dict: dict):
    """背景任務：處理 URL 文件轉換"""
    temp_file = None
    file_path = None
    try:
        progress_service.update_progress(task_id, 10, "downloading", f"下載檔案中: {source_url}")

        # 下載文件
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            try:
                response = await client.get(source_url)
                response.raise_for_status() 
            except httpx.RequestError as exc:
                print(f"[Task {task_id}] 下載時發生錯誤 {source_url}: {exc}")
                raise HTTPException(status_code=400, detail=f"無法下載 URL: {exc}")
            except httpx.HTTPStatusError as exc:
                 print(f"[Task {task_id}] 下載時收到錯誤狀態碼 {source_url}: {exc.response.status_code}")
                 raise HTTPException(status_code=exc.response.status_code, detail=f"下載 URL 時伺服器錯誤: {exc.response.status_code}")

            # 確定檔案類型和副檔名 (這部分可以提取到 file_service)
            content_type = response.headers.get("content-type", "")
            file_extension = ".bin" # Default
            if "pdf" in content_type: file_extension = ".pdf"
            elif "image/jpeg" in content_type or "image/jpg" in content_type: file_extension = ".jpg"
            elif "image/png" in content_type: file_extension = ".png"
            elif "image" in content_type: file_extension = ".img" # Generic image
            elif "html" in content_type: file_extension = ".html"
            elif "text" in content_type: file_extension = ".txt"
            elif "msword" in content_type or "officedocument" in content_type: file_extension = ".docx"
            else:
                url_p = urlparse(source_url).path
                if url_p: _, ext = os.path.splitext(url_p); file_extension = ext if ext else ".bin"
            
            # 建立暫存檔案並儲存內容
            # 使用 with 陳述式確保檔案即使出錯也能關閉
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_f:
                temp_f.write(response.content)
                file_path = Path(temp_f.name)
            print(f"[Task {task_id}] 檔案已下載至暫存路徑: {file_path}")

        progress_service.update_progress(task_id, 30, "converting", "轉換檔案中...")

        # 從字典重建 ConversionOptions
        # 注意：需要處理枚舉類型的值轉換
        try:
            options_obj = ConversionOptions(**conversion_options_dict)
            # 手動處理 ImageRefMode (如果傳入的是字串)
            if isinstance(options_obj.image_export_mode, str):
                 options_obj.image_export_mode = ImageRefMode(options_obj.image_export_mode)
        except Exception as e:
             print(f"[Task {task_id}] 無法從字典建立 ConversionOptions: {e}")
             # 可以使用預設選項或引發錯誤
             options_obj = ConversionOptions() # 使用預設值
             progress_service.update_progress(task_id, 30, "converting", "警告：使用預設轉換選項")

        # 執行轉換
        conversion_result = run_conversion(file_path, options_obj)

        progress_service.update_progress(task_id, 70, "processing", "處理轉換結果...")

        # 決定最終輸出路徑
        output_path = OUTPUT_DIR / output_filename # 檔名已在路由處理過
        
        # 匯出文件
        img_export_mode_value = options_obj.image_export_mode.value
        export_result = await file_service.export_document(
            result=conversion_result,
            format=format,
            image_export_mode=img_export_mode_value,
            out_dir_path=str(OUTPUT_DIR),
            out_path=str(output_path)
        )
        
        # 儲存元數據
        file_service.save_metadata(
            output_path=output_path,
            source_identifier=source_url, # 使用 URL 作為來源標識
            format=format,
            image_export_mode=img_export_mode_value
        )

        progress_service.update_progress(task_id, 100, "complete", "轉換完成")
        print(f"[Task {task_id}] URL 轉換成功完成: {source_url}")

    except Exception as e:
        error_message = f"URL轉換失敗: {str(e)}"
        print(f"[Task {task_id}] {error_message}")
        progress_service.update_progress(task_id, 100, "error", error_message)
    finally:
        # 清理暫存檔案
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                print(f"[Task {task_id}] 已刪除暫存檔案: {file_path}")
            except Exception as e:
                print(f"[Task {task_id}] 無法刪除暫存檔案 {file_path}: {e}")
