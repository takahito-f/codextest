"""Database models for the billing application."""

from __future__ import annotations

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator

from database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID."""

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_oid: Mapped[str] = mapped_column(GUID(), nullable=False)
    role_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("roles.role_id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_oid", "role_id", name="uq_user_roles_user_role"),
        Index("ix_user_roles_user_oid", "user_oid"),
    )


class TouchakuKanri(Base):
    __tablename__ = "touchaku_kanri"

    juryo_nichiji: Mapped[DateTime] = mapped_column(DateTime(timezone=False), primary_key=True)
    jigyosha_id: Mapped[str] = mapped_column(CHAR(15), primary_key=True)
    kakin_getsu: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    file_sakusei_date: Mapped[str] = mapped_column(CHAR(15), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sutoreji_path: Mapped[str] = mapped_column(String(100), nullable=False)
    appurodo_moto: Mapped[str] = mapped_column(String(100), nullable=False)
    torikomi_zumi_nichiji: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    file_bunkatsu_su: Mapped[int | None] = mapped_column(Numeric(2, 0), nullable=True)
    nbp_sakusei_nichiji: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    nbp_file_sakusei_nichiji: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    nbp_soshin_nichiji: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    status: Mapped[int] = mapped_column(Numeric(1, 0), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (Index("ix_touchaku_kanri_kakin_jigyosha_juryo", "kakin_getsu", "jigyosha_id", "juryo_nichiji"),)


class KakinJouhou(Base):
    __tablename__ = "kakin_jouhou"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_shikibetsu: Mapped[int] = mapped_column(Numeric(1, 0), nullable=False)
    record_no: Mapped[int] = mapped_column(Numeric(7, 0), nullable=False)
    jigyosha_id: Mapped[str] = mapped_column(CHAR(15), nullable=False)
    kakin_getsu: Mapped[str] = mapped_column(CHAR(6), nullable=False)
    bandoru_id: Mapped[str] = mapped_column(CHAR(16), nullable=False)
    riyosha_bango: Mapped[str] = mapped_column(CHAR(16), nullable=False)
    shohin_bango: Mapped[str] = mapped_column(CHAR(12), nullable=False)
    seikyuu_kingaku: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    goriyo_kaishi_date: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    goriyo_shuryo_date: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    seikyusho_hyoji_mongon: Mapped[str] = mapped_column(String(78), nullable=False)
    yobi_char: Mapped[str] = mapped_column(String(100), nullable=False)
    hosei_data_hyoji: Mapped[str | None] = mapped_column(CHAR(1))
    kaishu_jokyo: Mapped[str | None] = mapped_column(CHAR(1))
    saishu_seisan_hyoji: Mapped[str | None] = mapped_column(CHAR(1))
    pj_code: Mapped[str | None] = mapped_column(CHAR(10))
    toroku_nichiji: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    file_mei: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (Index("ix_kakin_jouhou_kakin_jigyosha", "kakin_getsu", "jigyosha_id"),)
