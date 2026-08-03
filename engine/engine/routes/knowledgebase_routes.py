from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from engine.config import DB_PATH
from engine.utils.logger import create_logger

log = create_logger("routes-kb")

router = APIRouter(prefix="/api/knowledgebase", tags=["knowledgebase"])


@router.get("")
async def get_knowledgebase(request: Request):
    if not DB_PATH.exists():
        return JSONResponse({
            "stats": {"pageCount": 0, "componentCount": 0, "navigationCount": 0, "apiEndpointCount": 0},
            "pages": [],
            "message": "No knowledgebase found. Run tests to build knowledge.",
        })

    from engine.knowledgebase.query import get_all_pages, get_api_endpoints, get_components_on_page, get_navigation_from, get_page_info, get_stats

    page_param = request.query_params.get("page")
    stats = get_stats()

    if page_param:
        page_info = get_page_info(page_param)
        components = get_components_on_page(page_param, 100)
        navigation = get_navigation_from(page_param)
        return JSONResponse({"stats": stats, "page": page_info, "components": components, "navigation": navigation})

    pages = get_all_pages(50)
    endpoints = get_api_endpoints(50)
    return JSONResponse({"stats": stats, "pages": pages, "endpoints": endpoints})
