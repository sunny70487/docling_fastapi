from fastapi import APIRouter, HTTPException

from config import ACTIVE_BATCH_TASKS, CONVERSION_PROGRESS

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("/")
async def list_tasks():
    """獲取所有活躍的批次處理任務"""
    tasks = []
    # 直接使用從 config 匯入的字典
    for task_id, task_info in ACTIVE_BATCH_TASKS.items():
        progress_info = CONVERSION_PROGRESS.get(task_id, {})
        tasks.append({
            "task_id": task_id,
            "created_at": task_info.get("created_at", 0),
            "file_count": task_info.get("file_count", 0),
            # 考慮是否返回 options 和 results
            "progress": progress_info.get("progress", 0),
            "status": progress_info.get("status", "unknown"),
            "message": progress_info.get("message", "")
        })
    
    return {"tasks": sorted(tasks, key=lambda x: x["created_at"], reverse=True)}

@router.get("/{task_id}")
async def get_task(task_id: str):
    """獲取特定任務的詳細資訊"""
    if task_id not in ACTIVE_BATCH_TASKS:
        raise HTTPException(status_code=404, detail="找不到該任務")
    
    task_info = ACTIVE_BATCH_TASKS[task_id]
    progress_info = CONVERSION_PROGRESS.get(task_id, {})
    
    return {
        "task_id": task_id,
        "created_at": task_info.get("created_at", 0),
        "file_count": task_info.get("file_count", 0),
        "results": task_info.get("results", []), # 返回結果
        "options": task_info.get("options", {}), # 返回選項
        "progress": progress_info.get("progress", 0),
        "status": progress_info.get("status", "unknown"),
        "message": progress_info.get("message", "")
    }

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """刪除特定的批次處理任務記錄"""
    if task_id not in ACTIVE_BATCH_TASKS:
        raise HTTPException(status_code=404, detail="找不到該任務")
    
    progress_info = CONVERSION_PROGRESS.get(task_id, {})
    # 考慮允許刪除錯誤狀態的任務
    if progress_info.get("status") not in ["complete", "error", "unknown", None]: 
         # 檢查是否正在進行中 (更精確的狀態列表)
         if progress_info.get("status") in ["init", "uploading", "downloading", "converting", "processing"]:
            raise HTTPException(status_code=400, detail="無法刪除正在處理中的任務")
    
    # 從活躍任務和進度記錄中刪除 (使用 pop 以安全地處理不存在的情況)
    ACTIVE_BATCH_TASKS.pop(task_id, None)
    CONVERSION_PROGRESS.pop(task_id, None)
    
    print(f"任務記錄已刪除: {task_id}")
    return {"status": "success", "message": "任務已刪除"}
