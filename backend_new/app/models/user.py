import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """
    Application user — written by auth service on registration.
    hashed_password stores a bcrypt digest; plaintext is never persisted.
    last_refresh_token stores a SHA-256 hash of the current refresh token
    to support single-use invalidation on rotation.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_subscriber: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_refresh_token: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # SHA-256 hash of current refresh token; raw token never stored
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} is_subscriber={self.is_subscriber}>"
