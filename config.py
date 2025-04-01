from pathlib import Path
from typing import Dict
from models import ConversionOptions # 從 models.py 匯入

# 建立儲存目錄
OUTPUT_DIR = Path("output")
UPLOADS_DIR = Path("uploads")
IMAGES_DIR = Path("static/images")
TEMPLATES_DIR = Path("templates")

OUTPUT_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True, parents=True)

# 全域變數來儲存轉換進度 (之後會考慮移到更合適的地方，例如 Service 或資料庫)
CONVERSION_PROGRESS: Dict[str, Dict] = {}

# 儲存活躍的批次任務 (之後會考慮移到更合適的地方，例如 Service 或資料庫)
ACTIVE_BATCH_TASKS: Dict[str, Dict] = {}

# 建立全域的預設設定
DEFAULT_CONVERSION_OPTIONS = ConversionOptions()

# 配置類別，提供統一的配置訪問點
class Config:
    """應用程式配置類別"""
    
    # 路徑設定
    OUTPUT_DIR = OUTPUT_DIR
    UPLOADS_DIR = UPLOADS_DIR
    IMAGES_DIR = IMAGES_DIR
    TEMPLATES_DIR = TEMPLATES_DIR
    
    # API 設定
    HOST = "0.0.0.0"
    PORT = 8000
    DEBUG = True
    
    # Docling 核心設定
    DOCLING_TIMEOUT = 120  # 秒
    
    # 預設選項
    DEFAULT_CONVERSION_OPTIONS = DEFAULT_CONVERSION_OPTIONS
