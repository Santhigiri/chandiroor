from typing import Any

def col(attr: Any) -> Any:
    """Escape hatch for SQLModel's known Pyright typing gap on class-attribute access.

    Pyright resolves `Model.some_field` to the field's declared Python type
    instead of the runtime `InstrumentedAttribute`/`QueryableAttribute` SQLModel's
    metaclass actually installs. This breaks type-checking for query clauses
    such as `.order_by()`, `.where()`, and `.selectinload()`. `col()` performs
    no runtime conversion — it returns its argument unchanged — and exists only
    to opt a call site out of this specific false positive.
    """
    return attr
