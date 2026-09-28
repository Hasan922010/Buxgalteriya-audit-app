from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.models.user import User
from app.services.task_manager import task_manager

router = APIRouter()

@router.get("/{task_id}")
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    """
    Returns the real-time execution progress and status of a background task owned by the caller.
    """
    task = task_manager.get_task(task_id)
    if not task or not (current_user.is_superuser or task.owner_id == str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {task_id} bo'lgan fon vazifasi topilmadi"
        )
    return task.to_dict()

@router.get("", response_model=List[Dict[str, Any]])
async def list_recent_tasks(current_user: User = Depends(get_current_user)):
    """
    Returns the caller's active or recent background tasks (all tasks for a superuser).
    """
    tasks = task_manager.tasks_visible_to(str(current_user.id), current_user.is_superuser)
    return [task.to_dict() for task in tasks]
