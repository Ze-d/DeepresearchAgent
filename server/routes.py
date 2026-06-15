# server/routes.py
import logging
import threading

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.tasks import task_manager, TaskStatus
from server.stream import sse_manager, sse_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ——— Request models ———


class CreateTaskRequest(BaseModel):
    query: str
    max_iterations: int = 2


class ReviewRequest(BaseModel):
    action: str  # "approve" | "amend" | "redo"
    notes: str = ""
    new_queries: list[str] = []


# ——— POST /api/tasks ———


@router.post("/tasks", status_code=202)
def create_task(req: CreateTaskRequest):
    """创建研究任务，立即返回 task_id，后台异步执行。"""
    task = task_manager.create(req.query, max_iterations=req.max_iterations)
    task_id = task["task_id"]

    # 后台执行 workflow
    def run_background():
        from deepresearch.cli import run_workflow

        task_manager.update(task_id, status=TaskStatus.RUNNING.value)
        sse_manager.put_event(
            task_id, "task_started", {"task_id": task_id}
        )

        try:
            result = run_workflow(req.query, max_iterations=req.max_iterations)
            task_manager.update(
                task_id,
                status=TaskStatus.COMPLETED.value,
                state={
                    "user_query": result.get("user_query"),
                    "research_plan": result.get("research_plan"),
                    "sources": result.get("sources"),
                    "evidences": result.get("evidences"),
                    "draft_summary": result.get("draft_summary"),
                    "critique_result": result.get("critique_result"),
                    "final_report": result.get("final_report"),
                    "iteration": result.get("iteration"),
                    "iteration_metrics": result.get("iteration_metrics"),
                    "citations": result.get("citations"),
                    "errors": result.get("errors"),
                },
            )
            sse_manager.put_event(
                task_id,
                "done",
                {
                    "status": "completed",
                    "final_report": result.get("final_report"),
                },
            )
        except Exception as e:
            logger.exception("Task %s failed", task_id)
            task_manager.update(
                task_id,
                status=TaskStatus.FAILED.value,
                error=str(e),
            )
            sse_manager.put_event(task_id, "error", {"error": str(e)})

    thread = threading.Thread(target=run_background, daemon=True)
    thread.start()

    return {"task_id": task_id, "status": task["status"]}


# ——— GET /api/tasks ———


@router.get("/tasks")
def list_tasks(limit: int = Query(20, ge=1, le=100)):
    """返回最近的任务列表。"""
    tasks = task_manager.list_tasks(limit=limit)
    return [
        {
            "task_id": t["task_id"],
            "query": t["query"],
            "status": t["status"],
            "created_at": t["created_at"],
        }
        for t in tasks
    ]


# ——— GET /api/tasks/{id} ———


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """查询单个任务的状态和完整 state。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task["task_id"],
        "query": task["query"],
        "status": task["status"],
        "max_iterations": task["max_iterations"],
        "state": task.get("state", {}),
        "error": task.get("error"),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


# ——— GET /api/tasks/{id}/stream ———


@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE 事件流：实时推送任务执行进度。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        sse_endpoint(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ——— GET /api/tasks/{id}/report ———


@router.get("/tasks/{task_id}/report")
def get_task_report(task_id: str):
    """返回任务的最终报告 Markdown。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != TaskStatus.COMPLETED.value:
        raise HTTPException(
            status_code=404, detail="Report not available (task not completed)"
        )
    state = task.get("state", {})
    return {
        "task_id": task_id,
        "final_report_md": state.get("final_report", ""),
    }


# ——— DELETE /api/tasks/{id} ———


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    """删除任务。"""
    if not task_manager.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")


# ——— POST /api/tasks/{id}/review ———


@router.post("/tasks/{task_id}/review")
def submit_review(task_id: str, req: ReviewRequest):
    """提交人工审核结果。"""
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update task with review decision
    task_manager.update(task_id,
        status=TaskStatus.RUNNING.value,
        review_decision={
            "action": req.action,
            "notes": req.notes,
            "new_queries": req.new_queries,
        })

    logger.info("Review submitted for task %s: action=%s", task_id, req.action)
    return {"status": "ok", "task_id": task_id, "action": req.action}
