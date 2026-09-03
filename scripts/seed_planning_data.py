"""灌入规划域种子数据（辅修专业 / 培养方案 / 岗位），用于本地开发和测试。"""

import asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from apps.api.config import settings
from apps.api.database import Base
from apps.api.models import Program, ProgramPlanItem, Job
from services.planning.recommendation_engine import PROGRAMS
from services.planning.course_planner import PROGRAM_PLANS
from services.planning.career_engine import SAMPLE_JOBS


async def main():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine)
    async with session_factory() as db:
        # 幂等：先删后插（先子表后父表）
        await db.execute(delete(ProgramPlanItem))
        await db.execute(delete(Program))
        await db.execute(delete(Job))

        for p in PROGRAMS:
            db.add(Program(**p))
        for name, items in PROGRAM_PLANS.items():
            for it in items:
                db.add(ProgramPlanItem(program_name=name, **it))
        for j in SAMPLE_JOBS:
            db.add(Job(**j))
        await db.commit()

        print(f"Programs: {len(PROGRAMS)}")
        print(f"ProgramPlanItems: {sum(len(v) for v in PROGRAM_PLANS.values())}")
        print(f"Jobs: {len(SAMPLE_JOBS)}")

    await engine.dispose()
    print("\n规划域种子数据加载完成！")


if __name__ == "__main__":
    asyncio.run(main())
