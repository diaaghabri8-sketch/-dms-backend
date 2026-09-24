from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import UTCDateTime
from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    expediteur_id: Mapped[int] = mapped_column(ForeignKey("techniciens.id"), nullable=False)

    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    envoye_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)
    lu_le: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    expediteur: Mapped["Technicien"] = relationship(back_populates="messages_envoyes")
