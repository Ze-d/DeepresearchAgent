# server/stream.py
import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class SSEManager:
    """管理 SSE 客户端连接和事件广播。

    每个 task_id 对应一个 asyncio.Queue，
    工作线程通过 put_event() 写入事件，
    SSE endpoint 通过 subscribe() 获取 queue。
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """订阅任务的 SSE 事件流，返回 queue。"""
        if task_id not in self._queues:
            self._queues[task_id] = asyncio.Queue()
        return self._queues[task_id]

    def put_event(self, task_id: str, event: str, data: dict[str, Any]) -> None:
        """向指定任务的事件流放入事件（线程安全）。"""
        if task_id not in self._queues:
            self._queues[task_id] = asyncio.Queue()
        q = self._queues[task_id]
        try:
            q.put_nowait((event, data))
        except asyncio.QueueFull:
            logger.warning(
                "SSE queue full for task %s, dropping event %s", task_id, event
            )

    def unsubscribe(self, task_id: str) -> None:
        """取消订阅，清理 queue。"""
        self._queues.pop(task_id, None)


# 全局单例
sse_manager = SSEManager()


async def sse_endpoint(task_id: str):
    """SSE 事件流 ASGI generator。"""
    q = sse_manager.subscribe(task_id)
    try:
        while True:
            try:
                event, data = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                yield (
                    f"event: heartbeat\n"
                    f"data: {json.dumps({'timestamp': time.time()})}\n\n"
                )
                continue

            yield f"event: {event}\n"
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n"
            yield "\n"

            if event in ("done", "error"):
                break
    except asyncio.CancelledError:
        pass
    finally:
        sse_manager.unsubscribe(task_id)
