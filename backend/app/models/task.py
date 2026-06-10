"""
任务模型 — 对应 MySQL tasks 表
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
        "comment": "文档生成任务表",
    }

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, comment="任务唯一标识"
    )
    doc_type: Mapped[str] = mapped_column(
        String(100), default="需求规格说明书", comment="文档类型"
    )
    custom_name: Mapped[str] = mapped_column(
        String(200), default="", comment="自定义文档名称"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
        comment="任务状态: pending/running/completed/failed",
    )
    material: Mapped[str] = mapped_column(
        Text, default="", comment="原始素材文本"
    )
    result_md: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="生成的 Markdown 文档"
    )
    outline_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="生成的大纲 JSON"
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败时的错误信息"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} status={self.status}>"
