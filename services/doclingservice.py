"""與 Docling 核心通訊的服務模組

提供與 Docling 核心通訊的函式，包括獲取文件內容、轉換格式等。
"""
from docling_core.types.doc import ImageRefMode
import json
from typing import Optional, Dict, Any, Union

# 這是一個模擬功能的簡單實現，實際應用中需要通過 docling 核心 API 獲取文件
# 在真實環境中，這些函數應該通過 API 或直接調用 docling 庫來實現

async def get_document_as_json(document_id: str) -> Dict[str, Any]:
    """獲取文件的 JSON 表示
    
    參數:
        document_id: 文件 ID
        
    返回:
        包含文件內容的 JSON 物件
    """
    # 實際使用中應該呼叫 docling 核心庫或 API 來獲取文件
    # 這裡僅提供一個簡單的模擬實現
    print(f"[doclingservice] 獲取文件 JSON 格式: {document_id}")
    
    # 假設文件內容在這裡從 docling 核心獲取
    # 這裡返回一個簡單的 JSON 物件作為範例
    return {
        "id": document_id,
        "type": "document",
        "content": f"Document content for {document_id}",
        "meta": {
            "created_at": "2023-04-01T00:00:00Z"
        }
    }

async def get_document_as_html(
    document_id: str, 
    image_mode: ImageRefMode = ImageRefMode.REFERENCED, 
    single_file: bool = False
) -> str:
    """獲取文件的 HTML 表示
    
    參數:
        document_id: 文件 ID
        image_mode: 圖片處理模式，可為 EMBEDDED (內嵌), REFERENCED (引用) 或 PLACEHOLDER (佔位符)
        single_file: 是否生成單一檔案 HTML
        
    返回:
        HTML 字串
    """
    print(f"[doclingservice] 獲取文件 HTML 格式: {document_id}, image_mode: {image_mode}, single_file: {single_file}")
    
    # 根據 image_mode 生成不同的 HTML
    if image_mode == ImageRefMode.EMBEDDED:
        # 假設這是一個帶有 base64 編碼圖片的 HTML
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Document {document_id}</title>
        </head>
        <body>
            <h1>Document {document_id}</h1>
            <p>This is a sample document with embedded image:</p>
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" alt="Sample image">
            <p>End of document.</p>
        </body>
        </html>
        """
    elif image_mode == ImageRefMode.PLACEHOLDER:
        # 使用佔位符代替圖片
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Document {document_id}</title>
        </head>
        <body>
            <h1>Document {document_id}</h1>
            <p>This is a sample document with placeholder image:</p>
            <!-- image -->
            <p>End of document.</p>
        </body>
        </html>
        """
    else:  # ImageRefMode.REFERENCED
        # 預設相對路徑引用
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Document {document_id}</title>
        </head>
        <body>
            <h1>Document {document_id}</h1>
            <p>This is a sample document with referenced image:</p>
            <img src="images/sample.png" alt="Sample image">
            <p>End of document.</p>
        </body>
        </html>
        """

async def get_document_as_markdown(
    document_id: str, 
    image_mode: ImageRefMode = ImageRefMode.REFERENCED
) -> str:
    """獲取文件的 Markdown 表示
    
    參數:
        document_id: 文件 ID
        image_mode: 圖片處理模式，可為 EMBEDDED (內嵌), REFERENCED (引用) 或 PLACEHOLDER (佔位符)
        
    返回:
        Markdown 字串
    """
    print(f"[doclingservice] 獲取文件 Markdown 格式: {document_id}, image_mode: {image_mode}")
    
    # 根據 image_mode 生成不同的 Markdown
    if image_mode == ImageRefMode.EMBEDDED:
        # 假設這是帶有 base64 編碼圖片的 Markdown
        return f"""
# Document {document_id}

This is a sample document with embedded image:

![Sample image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==)

End of document.
"""
    elif image_mode == ImageRefMode.PLACEHOLDER:
        # 使用佔位符代替圖片
        return f"""
# Document {document_id}

This is a sample document with placeholder image:

<!-- image -->

End of document.
"""
    else:  # ImageRefMode.REFERENCED
        # 預設相對路徑引用
        return f"""
# Document {document_id}

This is a sample document with referenced image:

![Sample image](images/sample.png)

End of document.
""" 