"""外部通知 worker。

默认 provider 为空，因此本地 mock/Docker 开发不会访问外部网络；配置 provider 后，
worker 会按通知记录中的 retry/backoff 状态处理 email、sms 或 webhook 渠道。
"""

import asyncio
import logging

from apps.api.config import settings
from apps.api.database import async_session, init_db
from apps.api.routes.notifications import (
    dispatch_external_notifications,
    enqueue_due_learning_reminders,
)

logger = logging.getLogger("fuxiaohe.notification_worker")


async def run_once() -> int:
    """执行一轮外部通知扫描，便于定时任务和测试复用。"""
    async with async_session() as db:
        reminders = await enqueue_due_learning_reminders(db)
        external = await dispatch_external_notifications(db)
        return reminders + external


async def main() -> None:
    await init_db()
    while True:
        processed = await run_once()
        if processed:
            logger.info("processed %s external notifications", processed)
        await asyncio.sleep(max(1, settings.notification_worker_interval_seconds))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
