from fastapi import Query
from typing import Optional


def get_pagination_params(
    page: Optional[int] = Query(1, ge=1, description="页码"),
    page_size: Optional[int] = Query(20, ge=1, le=100, description="每页数量"),
):
    return {"page": page, "page_size": page_size}


def paginate(query, page: int, page_size: int):
    """通用分页：返回 (items, total)"""
    total = query.count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    return items, total


def format_pagination_response(items: list, total: int, page: int, page_size: int):
    """统一分页响应格式"""
    return {
        "list": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
