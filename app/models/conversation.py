from datetime import datetime

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base

conversation_participants = Table(
    "conversation_participants",
    Base.metadata,
    Column("conversation_id", ForeignKey("conversations.id"), primary_key=True),
    Column("technicien_id", ForeignKey("techniciens.id"), primary_key=True),
    Column("date_ajout", UTCDateTime(), server_default=func.now(), nullable=False),
)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_group: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    participants: Mapped[list["Technicien"]] = relationship(
        secondary=conversation_participants, back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.envoye_le", cascade="all, delete-orphan"
    )
