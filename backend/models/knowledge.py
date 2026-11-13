"""Knowledge tables (additive): approved client facts and the approved source library.

  client_profiles     one row per client: brand voice, audience, services, locations, key
                      messages. Smriti loads it only when status = approved. Any edit sets it
                      back to draft; a different signed-in person approves it.
  knowledge_sources   pages a person added (pasted or fetched from an allowed site). Anvesh's
                      facts can be verified only against rows with status = approved; a
                      different signed-in person approves each one.
"""
from datetime import datetime

from sqlalchemy import INTEGER, JSON, TEXT, TIMESTAMP, VARCHAR, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    client_id: Mapped[str] = mapped_column(VARCHAR(50), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    brand_voice: Mapped[str] = mapped_column(TEXT, nullable=False, default="")
    audience: Mapped[str] = mapped_column(TEXT, nullable=False, default="")
    services: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    locations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    key_messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="draft")   # draft | approved
    version: Mapped[int] = mapped_column(INTEGER, nullable=False, default=1)
    updated_by: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    approved_by: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(VARCHAR(20), primary_key=True)                     # SRC-XXXXXX
    client_id: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True, index=True)  # None = shared
    title: Mapped[str] = mapped_column(VARCHAR(300), nullable=False)
    publisher: Mapped[str] = mapped_column(VARCHAR(200), nullable=False, default="")
    url: Mapped[str] = mapped_column(VARCHAR(1000), nullable=False, default="")
    topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    text: Mapped[str] = mapped_column(TEXT, nullable=False)
    content_hash: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    origin: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="pasted")   # pasted | fetched
    # proposed | approved | retired
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="proposed", index=True)
    added_by: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    added_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    retrieved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
