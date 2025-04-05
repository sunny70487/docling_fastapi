import json
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from config import OUTPUT_DIR, IMAGES_DIR
from services.file_service import sanitize_filename

router = APIRouter()

@router.get("/view/{filename}")
async def view_document(request: Request, filename: str):
    templates = request.app.state.templates
    
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="找不到檔案")

    content = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"讀取檔案時發生錯誤 {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"無法讀取檔案內容: {e}")

    # 根據檔案副檔名判斷格式
    format_type = "markdown" # default
    if filename.endswith(".json"):
        format_type = "json"
    elif filename.endswith(".yaml") or filename.endswith(".yml"):
        format_type = "yaml"
    elif filename.endswith(".html"):
        format_type = "html"
    elif filename.endswith(".txt"):
        format_type = "text"
    elif filename.endswith(".doctags"):
        format_type = "doctags"

    # 獲取來源資訊
    source_info = "未知來源"
    meta_path = file_path.with_suffix('.meta.json')
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as meta_f:
                meta_data = json.load(meta_f)
                source_info = meta_data.get("source", "無法讀取來源")
        except Exception as e:
            print(f"警告：無法讀取或解析元數據檔案 {meta_path}: {e}")
            source_info = "無法讀取來源資訊"

    return templates.TemplateResponse(
        "view.html",
        {
            "request": request,
            "filename": filename,
            "content": content,
            "format": format_type,
            "source_info": source_info
        }
    )

@router.get("/documents")
async def list_documents():
    """列出所有已轉換的輸出文件"""
    files = []
    supported_extensions = [".md", ".json", ".yaml", ".yml", ".html", ".txt", ".doctags"]
    try:
        for ext in supported_extensions:
            for file in OUTPUT_DIR.glob(f"*{ext}"):
                if file.name.endswith(".meta.json"): # 跳過 meta 檔案
                    continue
                
                format_type = "unknown"
                if ext == ".json": format_type = "json"
                elif ext in [".yaml", ".yml"]: format_type = "yaml"
                elif ext == ".html": format_type = "html"
                elif ext == ".txt": format_type = "text"
                elif ext == ".doctags": format_type = "doctags"
                elif ext == ".md": format_type = "markdown"
                    
                try:
                    stat_result = file.stat()
                    files.append({
                        "filename": file.name,
                        "created": stat_result.st_mtime,
                        "size": stat_result.st_size,
                        "format": format_type
                    })
                except Exception as stat_e:
                     print(f"無法獲取檔案狀態 {file.name}: {stat_e}")
                     # 可以選擇跳過此檔案或添加錯誤標記
                     files.append({
                        "filename": file.name,
                        "created": 0,
                        "size": 0,
                        "format": format_type,
                        "error": f"無法讀取狀態: {stat_e}"
                     })

        return {"documents": sorted(files, key=lambda x: x["created"], reverse=True)}
    except Exception as e:
        print(f"列出文件時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"無法列出文件: {e}")

@router.delete("/api/documents/{filename}", response_class=JSONResponse)
async def delete_document(filename: str):
    """刪除指定的輸出文件、元數據文件及其關聯的圖片目錄"""
    # 對傳入的檔名進行清理，防止路徑遍歷等問題
    # 雖然前端傳來的理論上應該是清理過的，但後端再次驗證更安全
    safe_filename = sanitize_filename(filename)
    if safe_filename != filename:
        # 如果清理前後不一致，說明原始檔名可能包含不安全字元，拒絕請求
        print(f"刪除請求被拒絕：原始檔名 '{filename}' 包含不安全字元。")
        raise HTTPException(status_code=400, detail="檔名包含無效字元")

    file_path = OUTPUT_DIR / safe_filename
    meta_path = file_path.with_suffix('.meta.json')
    
    # 確定關聯的圖片目錄路徑 (取檔名不含副檔名部分作為目錄名)
    file_basename = Path(safe_filename).stem
    image_dir_path = IMAGES_DIR / file_basename
    
    deleted_files = []
    errors = []

    # 刪除主文件
    try:
        if file_path.exists() and file_path.is_file():
            os.remove(file_path)
            deleted_files.append(str(file_path))
            print(f"已刪除文件: {file_path}")
        else:
            print(f"主文件未找到，無需刪除: {file_path}")
            # 即使主文件不存在，也可能存在孤立的 meta 文件，繼續嘗試刪除 meta
    except OSError as e:
        print(f"刪除文件時發生錯誤 {file_path}: {e}")
        errors.append(f"無法刪除文件 {safe_filename}: {e}")

    # 刪除元數據文件
    try:
        if meta_path.exists() and meta_path.is_file():
            os.remove(meta_path)
            deleted_files.append(str(meta_path))
            print(f"已刪除元數據文件: {meta_path}")
        else:
            print(f"元數據文件未找到，無需刪除: {meta_path}")
    except OSError as e:
        print(f"刪除元數據文件時發生錯誤 {meta_path}: {e}")
        # 即使主文件刪除成功，meta 刪除失敗也算錯誤
        errors.append(f"無法刪除元數據文件 {meta_path.name}: {e}")
        
    # 刪除關聯的圖片目錄
    try:
        if image_dir_path.exists() and image_dir_path.is_dir():
            # 使用 shutil.rmtree 刪除整個目錄及其內容
            shutil.rmtree(image_dir_path)
            deleted_files.append(f"圖片目錄: {image_dir_path}")
            print(f"已刪除圖片目錄: {image_dir_path}")
        else:
            print(f"圖片目錄不存在，無需刪除: {image_dir_path}")
    except OSError as e:
        print(f"刪除圖片目錄時發生錯誤 {image_dir_path}: {e}")
        errors.append(f"無法刪除圖片目錄 {image_dir_path.name}: {e}")

    if errors:
        # 如果有任何錯誤，返回失敗狀態
        raise HTTPException(status_code=500, detail="; ".join(errors))
    elif not deleted_files:
        # 如果兩個檔案和圖片目錄都沒找到（也沒出錯），認為是資源不存在
        raise HTTPException(status_code=404, detail="找不到要刪除的檔案")
    else:
        # 只要至少刪除了一個項目且沒有錯誤，就返回成功
        return {"message": f"成功刪除: {safe_filename}", "deleted": deleted_files}
