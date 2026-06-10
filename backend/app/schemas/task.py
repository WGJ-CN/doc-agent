"""
Pydantic 请求/响应模型
"""
import json
from datetime import datetime
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    material: str = Field(default="", description="素材文本内容")
    doc_type: str = Field(default="需求规格说明书", max_length=100)
    project_path: str | None = Field(default=None, description="项目路径（软件设计文档时用于代码扫描）")
    custom_name: str = Field(default="", max_length=200, description="自定义文档名称")


class TaskResponse(BaseModel):
    id: str
    doc_type: str
    custom_name: str
    status: str
    material: str
    result_md: str | None = None
    outline: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, task) -> "TaskResponse":
        outline = None
        if task.outline_json:
            try:
                outline = json.loads(task.outline_json)
            except json.JSONDecodeError:
                pass
        return cls(
            id=task.id,
            doc_type=task.doc_type,
            custom_name=task.custom_name,
            status=task.status,
            material=task.material,
            result_md=task.result_md,
            outline=outline,
            error=task.error,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    size: int
