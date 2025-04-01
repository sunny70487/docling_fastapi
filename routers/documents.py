import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse

from config import OUTPUT_DIR

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
