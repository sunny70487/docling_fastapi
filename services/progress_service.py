from config import CONVERSION_PROGRESS # 從 config 匯入全域進度字典

def update_progress(task_id: str, progress: int, status: str, message: str):
    """更新轉換進度"""
    # 注意：直接修改全域變數不是最佳實踐，之後可以考慮使用類別或更結構化的方式管理狀態
    CONVERSION_PROGRESS[task_id] = {
        "progress": progress,
        "status": status,
        "message": message
    }
