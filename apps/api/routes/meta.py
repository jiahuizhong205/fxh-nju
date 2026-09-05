"""产品元数据和功能目录 API。"""

from fastapi import APIRouter

router = APIRouter()

PRODUCT_METADATA = {
    "product_name": "福小禾",
    "tagline": "南大复合型人才学习助手",
    "version": "0.1.0",
    "birth_year": 2026,
    "team": "福小禾花园工作室",
    "features": [
        {"key": "recommendation", "name": "辅修方向推荐"},
        {"key": "planning", "name": "课程规划与冲突分析"},
        {"key": "career", "name": "职业探索"},
        {"key": "tutor", "name": "伴学问答"},
        {"key": "knowledge", "name": "知识森林"},
    ],
}


@router.get("/meta/product")
async def product_metadata():
    return PRODUCT_METADATA
