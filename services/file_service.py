import json
import yaml
import shutil
import uuid
import time
import os
from pathlib import Path
from typing import Optional, Dict
from fastapi import UploadFile
import re

# 從其他服務或 utils 匯入
from services.image_service import process_markdown_images, process_html_images
from docling_core.types.doc import ImageRefMode
from services import image_service, doclingservice
from config import UPLOADS_DIR, OUTPUT_DIR, Config

def save_uploaded_file(file: UploadFile) -> Path:
    """儲存上傳的檔案到 uploads 目錄"""
    try:
        file_path = UPLOADS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"檔案已儲存至: {file_path}")
        return file_path
    except Exception as e:
        print(f"儲存上傳檔案時發生錯誤: {e}")
        raise # 重新引發錯誤，讓上層處理

def get_file_extension(format: str) -> str:
    """根據格式獲取檔案副檔名"""
    if format == "markdown":
        return ".md"
    elif format == "text":
        return ".txt"
    elif format == "doctags":
        return ".doctags"
    else:
        return f".{format}"

def determine_output_path(original_filename: str, format: str, output_filename: Optional[str]) -> Path:
    """決定輸出檔案的路徑和名稱"""
    # 如果沒有提供輸出檔名，以原始檔名為基礎生成唯一名稱
    if not output_filename:
        output_filename = f"{Path(original_filename).stem}_{uuid.uuid4().hex}"
    
    # 獲取對應的副檔名
    file_extension = get_file_extension(format)
    if not output_filename.endswith(file_extension):
        output_filename = f"{output_filename.rstrip('.')}{file_extension}"
        
    output_path = OUTPUT_DIR / output_filename
    print(f"輸出檔案路徑設定為: {output_path}")
    return output_path

def save_metadata(output_path: Path, source_identifier: str, format: str, image_export_mode: str) -> None:
    """儲存轉換的元數據"""
    meta_path = output_path.with_suffix('.meta.json')
    meta_data = {
        "source": source_identifier, 
        "converted_at": time.time(),
        "format": format,
        "image_export_mode": image_export_mode,
    }
    try:
        with open(meta_path, "w", encoding="utf-8") as meta_f:
            json.dump(meta_data, meta_f, ensure_ascii=False, indent=2)
        print(f"元數據已儲存至: {meta_path}")
    except Exception as e:
        print(f"警告：無法儲存元數據檔案 {meta_path}: {e}")

# 用於從 UUID 中截取短識別符
UUID_SHORT_PATTERN = re.compile(r"^(.{8})[0-9a-f-]+$")

async def export_document(
    result=None,
    document_id=None,
    export_format=None,
    image_export_mode="referenced",
    out_dir_path=None,
    out_path=None,
    format=None,  # 向後兼容的參數名稱
    task_id=None,  # 用於圖片檔名的唯一 ID
    in_memory=False,
):
    """匯出文件到指定格式
    
    支援兩種不同的使用模式:
    1. 提供 result (轉換結果物件) + format + output_path
    2. 提供 document_id + export_format + out_path
    
    參數:
        result: 轉換結果 (DoclingConversionResult 物件)
        document_id: 文件 ID (如果不使用 result 參數)
        export_format/format: 匯出格式，可為 'html', 'html-single', 'markdown' 或 'json'
        image_export_mode: 圖片處理模式，可為 'embedded' (內嵌), 'referenced' (引用) 或 'placeholder' (佔位符)
        out_dir_path: 輸出目錄路徑，如果為 None，則使用設定中的默認路徑
        out_path/output_path: 輸出檔案完整路徑，如果提供，會覆蓋 out_dir_path
        task_id: 任務 ID (如果使用 result 參數)
        in_memory: 是否返回記憶體中的內容而非寫入檔案
    
    返回:
        包含輸出路徑和可選的內容的字典
    """
    # 處理向後兼容
    if format is not None and export_format is None:
        export_format = format
    
    if result is not None:
        print(f"[export_document] 使用 conversion_result 物件：{type(result)}")
        
        if not hasattr(result, 'document'):
            raise ValueError("提供的 result 物件沒有 document 屬性")
        
        # 使用傳入的 result.document 直接導出內容
        docling_document = result.document
        document_has_id = hasattr(docling_document, 'id')
        document_id = docling_document.id if document_has_id else str(uuid.uuid4())
        print(f"[export_document] 使用文件 ID: {document_id}" + ("" if document_has_id else " (生成的)"))
    elif document_id is None:
        raise ValueError("必須提供 result 或 document_id 參數")
    
    # 生成任務 ID (如果未提供)
    if task_id is None:
        task_id = str(uuid.uuid4())
    
    # 處理輸出路徑相關參數
    output_paths = {}
    output_content = {}
    
    # 從 document_id 或生成的 ID 中提取 basename
    if isinstance(document_id, str):
        # 嘗試移除可能的 UUID 部分
        file_basename = UUID_SHORT_PATTERN.sub(r"\1", document_id)
        if file_basename == document_id:  # 如果模式沒有匹配
            # 可能不是 UUID 格式，使用完整 ID
            file_basename = document_id
    else:
        file_basename = str(document_id)
    
    # 如果沒有指定輸出目錄，使用配置中的默認目錄
    out_dir_path = out_dir_path or Config.OUTPUT_DIR
    
    # 確保輸出目錄存在
    output_dir = Path(out_dir_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 處理圖片匯出模式
    # 注意：為了處理 docling 中產生的嵌入式圖片，我們改用下面的方法：
    # 1. 先以 EMBEDDED 模式獲取內容
    # 2. 如果要求的是 REFERENCED 模式，再將嵌入圖片轉為引用方式
    
    # 檢查 image_export_mode 是否有效
    valid_modes = {"embedded", "referenced", "placeholder"}
    if image_export_mode.lower() not in valid_modes:
        print(f"Warning: Unknown image_export_mode '{image_export_mode}'. Using 'referenced' as fallback.")
        image_export_mode = "referenced"
    else:
        image_export_mode = image_export_mode.lower()
    
    print(f"[export_document] Using image export mode: {image_export_mode}")
    
    # 始終使用 EMBEDDED 模式從 docling 獲取內容
    docling_image_mode = ImageRefMode.EMBEDDED
    print(f"[export_document] Requesting content from docling with mode: {docling_image_mode}")
    
    # 創建共享的參數字典
    process_params = {
        "task_id": task_id,
        "image_export_mode": image_export_mode,
        "output_base_name": Path(out_path).stem if out_path else file_basename,
        "output_dir_path": output_dir
    }
    
    # --- 對於 result 模式 ---
    if result is not None:
        # JSON 格式不處理圖片
        if export_format == "json":
            if out_path:
                output_path = Path(out_path)
            else:
                output_path = output_dir / f"{file_basename}.json"
            
            # 直接從 result.document 獲取 JSON
            json_data = result.document.export_to_dict()
            
            if in_memory:
                output_content["json"] = json.dumps(json_data, ensure_ascii=False, indent=2)
                output_paths["json"] = str(output_path)
                return {"paths": output_paths, "content": output_content}
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return {"paths": {"json": str(output_path)}}
        
        # 處理 HTML 匯出
        if export_format in ["html", "html-single"]:
            if out_path:
                output_path = Path(out_path)
            else:
                output_path = output_dir / f"{file_basename}.html"
            
            # 獲取 HTML，以 EMBEDDED 模式
            html_content = result.document.export_to_html(image_mode=docling_image_mode)
            
            # 如果需要引用模式，處理圖片並更新內容
            if image_export_mode == "referenced":
                # 處理嵌入式圖片，將它們轉換為引用
                html_content = process_html_images(
                    html_content, **process_params
                )
            
            # 如果是記憶體模式，直接返回內容
            if in_memory:
                output_content["html"] = html_content
                output_paths["html"] = str(output_path)
                return {"paths": output_paths, "content": output_content}
            
            # 寫入檔案
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            output_paths["html"] = str(output_path)
        
        # 處理 Markdown 匯出
        if export_format == "markdown":
            if out_path:
                output_path = Path(out_path)
            else:
                output_path = output_dir / f"{file_basename}.md"
            
            # 獲取 Markdown，以 EMBEDDED 模式
            markdown_content = result.document.export_to_markdown(image_mode=docling_image_mode)
            
            # 如果需要引用模式，處理圖片並更新內容
            if image_export_mode == "referenced":
                # 處理嵌入式圖片，將它們轉換為引用
                markdown_content = process_markdown_images(
                    markdown_content, **process_params
                )
            
            # 如果是記憶體模式，直接返回內容
            if in_memory:
                output_content["markdown"] = markdown_content
                output_paths["markdown"] = str(output_path)
                return {"paths": output_paths, "content": output_content}
            
            # 寫入檔案
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            output_paths["markdown"] = str(output_path)
        
        return {"paths": output_paths}
    
    # --- 對於 document_id 模式 ---
    else:
        # JSON 格式不處理圖片
        if export_format == "json":
            if out_path:
                output_path = Path(out_path)
            else:
                output_path = output_dir / f"{file_basename}.json"
            
            document_json = await doclingservice.get_document_as_json(document_id)
            
            if in_memory:
                output_content["json"] = document_json
                output_paths["json"] = str(output_path)
                return {"paths": output_paths, "content": output_content}
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(document_json, f, ensure_ascii=False, indent=2)
            
            return {"paths": {"json": str(output_path)}}
        
        # 處理 HTML 匯出
        if export_format in ["html", "html-single"]:
            if out_path:
                output_path = Path(out_path)
            else:
                output_path = output_dir / f"{file_basename}.html"
            
            # 從 docling 獲取 HTML 內容，使用 EMBEDDED 模式
            html_content = await doclingservice.get_document_as_html(
                document_id, docling_image_mode, single_file=export_format == "html-single"
            )
            
            # 如果需要引用模式，處理圖片並更新內容
            if image_export_mode == "referenced":
                # 處理嵌入式圖片，將它們轉換為引用
                html_content = process_html_images(
                    html_content, **process_params
                )
            
            # 如果是記憶體模式，直接返回內容
            if in_memory:
                output_content["html"] = html_content
                output_paths["html"] = str(output_path)
                return {"paths": output_paths, "content": output_content}
            
            # 寫入檔案
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            output_paths["html"] = str(output_path)
        
        # 處理 Markdown 匯出
        if export_format == "markdown":
            if out_path:
                output_path = Path(out_path)
            else:
                output_path = output_dir / f"{file_basename}.md"
            
            # 從 docling 獲取 Markdown 內容，使用 EMBEDDED 模式
            markdown_content = await doclingservice.get_document_as_markdown(document_id, docling_image_mode)
            
            # 如果需要引用模式，處理圖片並更新內容
            if image_export_mode == "referenced":
                # 處理嵌入式圖片，將它們轉換為引用
                markdown_content = process_markdown_images(
                    markdown_content, **process_params
                )
            
            # 如果是記憶體模式，直接返回內容
            if in_memory:
                output_content["markdown"] = markdown_content
                output_paths["markdown"] = str(output_path)
                return {"paths": output_paths, "content": output_content}
            
            # 寫入檔案
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            output_paths["markdown"] = str(output_path)
        
        return {"paths": output_paths}
