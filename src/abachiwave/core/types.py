from enum import StrEnum
from typing import Any

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import String, TypeDecorator


class EnumString[E: StrEnum](TypeDecorator[E]):
    """Store a ``StrEnum`` as its value while loading it back as the enum member.

    The columns this replaces were declared ``Mapped[SomeStrEnum]`` but typed as a
    bare ``String``: freshly constructed objects held an enum member, rows loaded
    from the database handed back a plain ``str``, and mypy could not tell the two
    apart. Anything reaching for ``.value`` on a loaded row raised ``AttributeError``
    at runtime.

    The on-disk representation is unchanged -- the emitted DDL is still
    ``VARCHAR(length)`` and the stored bytes are still the enum's value -- so
    swapping a column over needs no migration.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_type: type[E], length: int) -> None:
        self.enum_type = enum_type
        # Kept alongside the impl's own length so ``copy`` has a typed source for it:
        # ``self.impl`` is the String *class* to a type checker, only an instance at
        # runtime.
        self.length = length
        super().__init__(length=length)

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        """Accept either an enum member or its raw value; always store the value."""
        if value is None:
            return None
        return self.enum_type(value).value

    def process_result_value(self, value: Any, dialect: Dialect) -> E | None:
        """Coerce the stored string back into the enum member the annotation promises.

        A value outside the enum means the row is corrupt; raising here surfaces
        that instead of silently handing back the ``str`` this type exists to remove.
        """
        if value is None:
            return None
        return self.enum_type(value)

    @property
    def python_type(self) -> type[E]:
        """Report the enum, so the column is introspectable as what it actually yields."""
        return self.enum_type

    def copy(self, /, **kwargs: Any) -> "EnumString[E]":
        return EnumString(self.enum_type, self.length)
