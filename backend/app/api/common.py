import math
from fastapi import Query


def page_params(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    return page, page_size


def paged(items, total, page, page_size):
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size))}


def like(q: str) -> str:
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"
