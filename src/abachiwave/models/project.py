from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base
from abachiwave.core.types import EnumString


class ProjectStatus(StrEnum):
    active = "active"
    archived = "archived"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        EnumString(ProjectStatus, 16),
        nullable=False,
        default=ProjectStatus.active,
        server_default=ProjectStatus.active.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
