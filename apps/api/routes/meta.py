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

LEGAL_DOCUMENTS = {
    "review_required": True,
    "documents": [
        {
            "key": "terms",
            "title": "服务条款（待审核草案）",
            "status": "draft",
            "content": "福小禾用于提供学习规划、辅修信息整理和职业探索辅助，不替代南京大学教务或院系的正式审核、选课和通知。用户应以学校最新官方文件为准。",
        },
        {
            "key": "privacy",
            "title": "隐私说明（待审核草案）",
            "status": "draft",
            "content": "服务可能保存账号、画像、学习记录、课程规划、通知偏好和用户主动提交的反馈附件，用于提供对应功能。服务不会在同步快照中导出密码、登录令牌或验证码摘要；启用外部消息供应商前应另行完成配置和合规评估。",
        },
        {
            "key": "open_source",
            "title": "开源与版权说明（待审核草案）",
            "status": "draft",
            "content": "项目中的代码、数据、图片和第三方依赖分别受其适用的许可证或授权约束。正式许可证清单、第三方素材归属和版权联系方式待项目方确认后发布。",
        },
    ],
}


@router.get("/meta/product")
async def product_metadata():
    return PRODUCT_METADATA


@router.get("/meta/legal")
def get_legal_documents():
    """返回可展示的法律/版权草案；正式发布前必须经过项目方审核。"""
    return LEGAL_DOCUMENTS
