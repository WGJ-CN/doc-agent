"""
任务管理 REST 端点
"""
import uuid
import asyncio
import json
import os
import subprocess
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskResponse, TaskListResponse
from app.services.generator import DocumentGenerator, run_with_progress, _progress_buffers, _buffers_lock
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/browse-folder")
async def browse_folder():
    """调用操作系统原生文件夹选择对话框，返回所选路径"""
    try:
        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(None, _open_folder_dialog)
        if not path:
            raise HTTPException(status_code=400, detail="未选择文件夹")
        return {"path": path}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("打开文件夹对话框失败")
        raise HTTPException(status_code=500, detail=str(e))


def _open_folder_dialog():
    if os.name == "nt":
        path = _open_folder_dialog_tk()  # tkinter 秒出，PowerShell 做降级
        return path or _open_folder_dialog_windows()
    else:
        return _open_folder_dialog_tk()


def _open_folder_dialog_windows():
    ps_script = '''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "请选择项目文件夹"
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
'''
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        path = result.stdout.strip()
        return path if path else None
    except Exception:
        return _open_folder_dialog_tk()


def _open_folder_dialog_tk():
    try:
        import tkinter.filedialog
        import tkinter
    except ImportError:
        return None
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = tkinter.filedialog.askdirectory(title="请选择项目文件夹")
    root.destroy()
    return path if path else None


@router.post("", status_code=201)
async def create_task(
    req: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建文档生成任务"""
    task_id = uuid.uuid4().hex[:16]

    project_path = req.project_path if req.doc_type == "软件设计文档" else None
    effective_name = req.custom_name.strip() or req.doc_type

    task = Task(
        id=task_id,
        doc_type=req.doc_type,
        custom_name=req.custom_name.strip(),
        status="pending",
        material=req.material,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    asyncio.create_task(_execute_generation(task_id, project_path, effective_name))
    return TaskResponse.from_orm_model(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """分页查询历史任务"""
    count_stmt = select(func.count()).select_from(Task)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Task)
        .order_by(desc(Task.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[TaskResponse.from_orm_model(t) for t in tasks],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询单个任务状态与结果"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskResponse.from_orm_model(task)


@router.get("/{task_id}/stream")
async def stream_progress(task_id: str):
    """SSE 端点：先回放已有事件，再实时推送新事件（支持刷新后重连）"""
    async def event_generator():
        # 等待缓冲区创建
        while True:
            with _buffers_lock:
                buf = _progress_buffers.get(task_id)
            if buf is not None:
                break
            await asyncio.sleep(0.1)

        last_index = 0

        while True:
            # 回放未发送的事件（首次连接全部回放，重连补发新事件）
            with _buffers_lock:
                buf = _progress_buffers.get(task_id)
                if buf is None:
                    break
                while last_index < len(buf):
                    data = buf[last_index]
                    last_index += 1
                    yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    if data.get("step") == "done" and data.get("status") == "done":
                        return

            # 等待新事件
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}/download")
async def download_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """下载生成的文件"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if task.doc_type == "测试用例":
        file_path = os.path.join(settings.output_dir, f"{task_id}.md")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        filename = f"{task.doc_type}_{task_id}.md"
        return FileResponse(file_path, media_type="text/markdown", filename=filename)
    else:
        file_path = os.path.join(settings.output_dir, f"{task_id}.md")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        display_name = task.custom_name or task.doc_type
        filename = f"{display_name}_{task_id}.md"
        return FileResponse(file_path, media_type="text/markdown", filename=filename)


@router.delete("/{task_id}", status_code=200)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除任务及关联文件"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    await db.delete(task)
    await db.commit()

    for suffix in [".md", "_outline.json", "_material.txt"]:
        p = os.path.join(settings.output_dir, f"{task_id}{suffix}")
        if os.path.exists(p):
            os.remove(p)

    return {"deleted": task_id}


async def _execute_generation(task_id: str, project_path=None, full_doc_name=None):
    """后台执行文档生成，更新数据库状态（通过 run_with_progress 自动推送步骤进度）"""
    from app.database import async_session_factory

    # 创建回放缓冲区
    buf = []
    with _buffers_lock:
        _progress_buffers[task_id] = buf

    try:
        async with async_session_factory() as db:
            task = await db.get(Task, task_id)
            if not task:
                return

            task.status = "running"
            await db.commit()

            try:
                result_md, outline, error = await asyncio.to_thread(
                    run_with_progress,
                    task_id=task_id,
                    material=task.material,
                    doc_type=task.doc_type,
                    project_path=project_path,
                    full_doc_name=full_doc_name,
                )
            except Exception as e:
                result_md, outline, error = None, None, str(e)

            if error:
                task.status = "failed"
                task.error = error
            else:
                task.status = "completed"
                task.result_md = result_md
                task.outline_json = json.dumps(outline, ensure_ascii=False) if outline else None

            await db.commit()
    finally:
        # 保留缓冲区供 SSE 消费，延迟清理
        await asyncio.sleep(10)
        with _buffers_lock:
            _progress_buffers.pop(task_id, None)