from typing import TYPE_CHECKING, List

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.thithi import Thithi


class Paksha(SQLModel, table=True):
    """Moon phase grouping — Shukla (waxing) or Krishna (waning)."""

    __tablename__ = "paksha" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1=SHUKLA, 2=KRISHNA
    name: str = Field(unique=True)       # Python enum member name
    ml:   str                            # Malayalam label
    en:   str                            # English label

    thithis: List["Thithi"] = Relationship(back_populates="paksha")
