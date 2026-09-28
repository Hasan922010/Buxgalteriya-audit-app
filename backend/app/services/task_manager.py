import uuid
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional, Callable

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskInfo:
    def __init__(self, task_id: str, task_name: str, owner_id: Optional[str] = None):
        self.id = task_id
        self.owner_id = owner_id
        self.name = task_name
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.step_message = "Vazifa navbatga qo'yildi..."
        self.total_items = 0
        self.processed_items = 0
        self.error_message: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def update_progress(self, progress: int, step_message: str, processed_items: int = 0, total_items: int = 0):
        self.status = TaskStatus.PROCESSING
        self.progress = min(max(progress, 0), 100)
        self.step_message = step_message
        if processed_items:
            self.processed_items = processed_items
        if total_items:
            self.total_items = total_items
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def complete(self, result: Dict[str, Any], message: str = "Muvaffaqiyatli yakunlandi"):
        self.status = TaskStatus.COMPLETED
        self.progress = 100
        self.step_message = message
        self.result = result
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def fail(self, error_message: str):
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.step_message = f"Xatolik: {error_message}"
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "progress": self.progress,
            "step_message": self.step_message,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "error_message": self.error_message,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

class TaskManager:
    """
    In-memory asynchronous background task manager with real-time progress tracking.
    Enables long-running Excel and statement imports without HTTP timeouts.
    """
    _tasks: Dict[str, TaskInfo] = {}

    @classmethod
    def create_task(cls, task_name: str, owner_id: Optional[str] = None) -> TaskInfo:
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(task_id=task_id, task_name=task_name, owner_id=owner_id)
        cls._tasks[task_id] = task_info
        return task_info

    @classmethod
    def get_task(cls, task_id: str) -> Optional[TaskInfo]:
        return cls._tasks.get(task_id)

    @classmethod
    def tasks_visible_to(cls, owner_id: str, is_superuser: bool = False) -> List[TaskInfo]:
        return [t for t in cls._tasks.values() if is_superuser or t.owner_id == owner_id]

    @classmethod
    def run_coroutine(cls, task_id: str, coro_func: Callable[[TaskInfo], Any]):
        """Spawns coroutine as background task on running asyncio event loop."""
        task_info = cls.get_task(task_id)
        if not task_info:
            return

        async def _wrapper():
            try:
                task_info.status = TaskStatus.PROCESSING
                await coro_func(task_info)
            except Exception as e:
                task_info.fail(str(e))

        asyncio.create_task(_wrapper())

task_manager = TaskManager()
