"""云端同步 worker；未配置 provider 时安全空转。"""

import asyncio
import logging

from sqlalchemy import select

from apps.api.config import settings
from apps.api.database import async_session, init_db
from apps.api.models import User
from apps.api.routes.sync import push_user_snapshot_to_provider

logger = logging.getLogger("fuxiaohe.sync_worker")


async def run_once() -> int:
    """扫描账号并推送最新脱敏快照，便于定时任务和测试复用。"""
    if not settings.sync_provider_url.strip():
        return 0
    processed = 0
    async with async_session() as db:
        result = await db.execute(select(User).order_by(User.created_at))
        for user in result.scalars().all():
            await push_user_snapshot_to_provider(db, user)
            processed += 1
    return processed


async def main() -> None:
    await init_db()
    while True:
        processed = await run_once()
        if processed:
            logger.info("processed %s sync accounts", processed)
        await asyncio.sleep(max(30, settings.sync_worker_interval_seconds))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
