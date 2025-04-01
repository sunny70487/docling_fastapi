import uuid
import os
from typing import Optional, Literal, List
from urllib.parse import urlparse
from fastapi import (
    APIRouter, Form, UploadFile, File, HTTPException, 
    Query, BackgroundTasks, Depends, Request
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from models import ConversionOptions
from services import file_service, conversion_service, progress_service
from docling_core.types.doc import ImageRefMode
from docling.datamodel.pipeline_options import (
    PdfPipeline, VlmModelType, EasyOcrOptions, PdfBackend, TableFormerMode, AcceleratorDevice
)
from config import ACTIVE_BATCH_TASKS, TEMPLATES_DIR # Import batch tasks dict and templates dir
import time

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/file-convert", response_class=HTMLResponse)
async def file_convert_page(request: Request):
    """統一的檔案轉換頁面，支援單一和批量檔案轉換功能"""
    return templates.TemplateResponse("batch_convert.html", {"request": request})


@router.get("/convert-url")
async def convert_url(
    background_tasks: BackgroundTasks,
    source: str = Query(..., description="文件 URL 地址"),
    output_filename: Optional[str] = Query(None, description="輸出檔案名稱"),
    format: Literal["markdown", "json", "yaml", "html", "text", "doctags"] = Query("markdown", description="輸出格式"),
    image_export_mode: ImageRefMode = Query(ImageRefMode.REFERENCED, description="圖片匯出模式"),
    pipeline: PdfPipeline = Query(PdfPipeline.STANDARD, description="PDF 處理管道"),
    vlm_model: VlmModelType = Query(VlmModelType.SMOLDOCLING, description="VLM 模型"),
    ocr: bool = Query(True, description="啟用 OCR"),
    force_ocr: bool = Query(False, description="強制 OCR"),
    ocr_engine: str = Query(EasyOcrOptions.kind, description="OCR 引擎"),
    ocr_lang: Optional[str] = Query(None, description="OCR 語言 (逗號分隔)"),
    pdf_backend: PdfBackend = Query(PdfBackend.DLPARSE_V2, description="PDF 後端"),
    table_mode: TableFormerMode = Query(TableFormerMode.ACCURATE, description="表格模式"),
    enrich_code: bool = Query(False, description="豐富化程式碼"),
    enrich_formula: bool = Query(False, description="豐富化公式"),
    enrich_picture_classes: bool = Query(False, description="圖片分類"),
    enrich_picture_description: bool = Query(False, description="圖片描述"),
    num_threads: int = Query(4, description="線程數"),
    device: AcceleratorDevice = Query(AcceleratorDevice.AUTO, description="加速器裝置")
):
    if not source.startswith(('http://', 'https://')):
        raise HTTPException(status_code=422, detail="無效的URL格式。URL必須以 http:// 或 https:// 開頭。")

    task_id = str(uuid.uuid4())
    
    # 決定輸出檔名
    final_output_filename = output_filename # Start with user provided
    if not final_output_filename:
        url_path = urlparse(source).path
        base_name = os.path.basename(url_path) if url_path and os.path.basename(url_path) else "document_from_url"
        # Use determine_output_path to handle unique name and extension
        # Need the original filename part for stem, use base_name
        temp_path_for_naming = file_service.determine_output_path(base_name, format, None) 
        final_output_filename = temp_path_for_naming.name # Get the final name with extension
    else:
        # Ensure provided filename has correct extension
        ext = file_service.get_file_extension(format)
        if not final_output_filename.endswith(ext):
            final_output_filename = f"{final_output_filename.rstrip('.')}{ext}"

    # 初始化進度
    progress_service.update_progress(task_id, 0, "queued", "已加入佇列，準備下載")

    # 建立選項字典以傳遞給背景任務
    options_dict = ConversionOptions(
         image_export_mode=image_export_mode,
         pipeline=pipeline, vlm_model=vlm_model, ocr=ocr, force_ocr=force_ocr,
         ocr_engine=ocr_engine, ocr_lang=ocr_lang, pdf_backend=pdf_backend,
         table_mode=table_mode, enrich_code=enrich_code, enrich_formula=enrich_formula,
         enrich_picture_classes=enrich_picture_classes, enrich_picture_description=enrich_picture_description,
         num_threads=num_threads, device=device
    ).dict()

    # 將任務添加到背景
    background_tasks.add_task(
        conversion_service.process_url_conversion_task,
        task_id=task_id,
        source_url=source,
        output_filename=final_output_filename,
        format=format,
        conversion_options_dict=options_dict
    )

    return {
        "status": "success",
        "message": "URL 轉換已加入背景佇列",
        "task_id": task_id,
        "output_filename": final_output_filename
    }

@router.post("/batch-convert")
async def batch_convert(
    # Use same parameters as original endpoint
    files: List[UploadFile] = File(...),
    format: Literal["markdown", "json", "yaml", "html", "text", "doctags"] = Form("markdown"),
    image_export_mode: ImageRefMode = Form(ImageRefMode.REFERENCED),
    pipeline: PdfPipeline = Form(PdfPipeline.STANDARD),
    vlm_model: VlmModelType = Form(VlmModelType.SMOLDOCLING),
    ocr: bool = Form(True),
    force_ocr: bool = Form(False),
    ocr_engine: str = Form(EasyOcrOptions.kind),
    ocr_lang: Optional[str] = Form(None),
    pdf_backend: PdfBackend = Form(PdfBackend.DLPARSE_V2),
    table_mode: TableFormerMode = Form(TableFormerMode.ACCURATE),
    enrich_code: bool = Form(False),
    enrich_formula: bool = Form(False),
    enrich_picture_classes: bool = Form(False),
    enrich_picture_description: bool = Form(False),
    num_threads: int = Form(4),
    device: AcceleratorDevice = Form(AcceleratorDevice.AUTO)
):
    task_id = uuid.uuid4().hex
    results = []
    total_files = len(files)

    # Create ConversionOptions object from Form data
    options = ConversionOptions(
        image_export_mode=image_export_mode,
        pipeline=pipeline, vlm_model=vlm_model, ocr=ocr, force_ocr=force_ocr,
        ocr_engine=ocr_engine, ocr_lang=ocr_lang, pdf_backend=pdf_backend,
        table_mode=table_mode, enrich_code=enrich_code, enrich_formula=enrich_formula,
        enrich_picture_classes=enrich_picture_classes, enrich_picture_description=enrich_picture_description,
        num_threads=num_threads, device=device
    )

    # Initialize batch task record and progress
    ACTIVE_BATCH_TASKS[task_id] = {
        "created_at": time.time(),
        "file_count": total_files,
        "results": [],
        "options": options.dict(), # Store options used for this batch
        "status": "init"
    }
    progress_service.update_progress(task_id, 0, "init", "初始化檔案轉換")

    img_export_mode_value = image_export_mode.value if hasattr(image_export_mode, 'value') else image_export_mode

    for i, file in enumerate(files):
        current_progress = int(((i + 0.5) / total_files) * 100) # Progress midway through file
        progress_service.update_progress(task_id, current_progress, "processing", f"處理檔案 {i+1}/{total_files}: {file.filename}")
        
        uploaded_file_path = None
        file_result = {"original_filename": file.filename, "status": "pending", "output_filename": None}

        try:
            # 1. Save uploaded file
            uploaded_file_path = file_service.save_uploaded_file(file)

            # 2. Determine output path (provide None for output_filename to generate unique)
            output_path = file_service.determine_output_path(
                original_filename=file.filename, 
                format=format, 
                output_filename=None 
            )
            output_filename_final = output_path.name

            # 3. Run conversion
            conversion_result = conversion_service.run_conversion(uploaded_file_path, options)

            # 4. Export document
            content = None
            export_result = await file_service.export_document(
                result=conversion_result,
                format=format,
                image_export_mode=img_export_mode_value,
                out_path=str(output_path)
            )
            if format in export_result.get("content", {}):
                content = export_result["content"][format]
            else:
                # 如果內容不在返回中，可能是因為沒有使用 in_memory=True
                paths = export_result.get("paths", {})
                if format in paths:
                    print(f"文件已匯出至: {paths[format]}")

            # 5. Save metadata
            file_service.save_metadata(
                output_path=output_path,
                source_identifier=file.filename,
                format=format,
                image_export_mode=img_export_mode_value
            )

            # Update result for this file
            file_result["status"] = "success"
            file_result["output_filename"] = output_filename_final
            print(f"[Task {task_id}] 成功處理檔案: {file.filename} -> {output_filename_final}")

        except Exception as e:
            error_message = str(e)
            file_result["status"] = "error"
            file_result["error"] = error_message
            print(f"[Task {task_id}] 處理檔案失敗: {file.filename} - {error_message}")
            # Update progress with error for this specific file if desired
            # progress_service.update_progress(task_id, current_progress, "error", f"處理檔案失敗 {i+1}/{total_files}: {file.filename} - {error_message}")
        finally:
             # Store result (success or error) for this file
             results.append(file_result)
             ACTIVE_BATCH_TASKS[task_id]["results"].append(file_result)
             # Optional: Clean up uploaded file immediately if needed
             # if uploaded_file_path and uploaded_file_path.exists():
             #     uploaded_file_path.unlink()
             pass

    # Final progress update for the batch
    success_count = len([r for r in results if r["status"] == "success"])
    final_status = "complete" if success_count == total_files else "partial_error"
    final_message = f"檔案轉換完成: 成功 {success_count}/{total_files} 檔案"
    if success_count < total_files:
         final_message += f", 失敗 {total_files - success_count}"
         ACTIVE_BATCH_TASKS[task_id]["status"] = "error" # Mark batch task as having errors
    else:
        ACTIVE_BATCH_TASKS[task_id]["status"] = "complete"
        
    progress_service.update_progress(task_id, 100, final_status, final_message)

    return {
        "status": final_status, # Reflect overall batch status
        "message": final_message,
        "task_id": task_id,
        "total_files": total_files,
        "results": results # Return detailed results for each file
    }

# 可以在這裡添加其他與轉換相關的路由 