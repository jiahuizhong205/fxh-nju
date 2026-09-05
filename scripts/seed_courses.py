"""把 scripts/fetched/courses_campus*.json 灌入 courses 表。

用法: PYTHONPATH=. python scripts/seed_courses.py [campus_code ...]
不传参数默认灌所有已抓取的 courses_campus*.json；传则只灌指定校区。
"""

import asyncio
import glob
import json
import sys

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from apps.api.config import settings
from apps.api.database import Base
from apps.api.models import Course

SOURCE = "xk.nju.edu.cn"


def _to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_schedule(course: dict) -> list[dict]:
    schedule = []
    for item in course.get("teachingTimeList") or []:
        schedule.append({
            "day": _to_int(item.get("dayOfWeek")),
            "start": _to_int(item.get("beginSection")),
            "end": _to_int(item.get("endSection")),
            "week": item.get("weekName") or "",
        })
    return schedule


def _to_course(c: dict) -> Course:
    # ponytail: 接口数值字段全是字符串，需安全转换；选课名额(已选/容量/满员)是选课时用的，不入库
    return Course(
        teaching_class_id=c["teachingClassID"],
        course_number=c.get("courseNumber") or "",
        course_name=c.get("courseName") or "",
        teacher=c.get("teacherName") or "",
        credit=_to_float(c.get("credit")),
        hours=_to_int(c.get("hours")),
        teaching_class_type=c.get("teachingClassType") or "KZY",
        campus=c.get("campusName") or "",
        department=c.get("departmentName") or "",
        teaching_place=c.get("teachingPlace") or "",
        school_term=c.get("schoolTerm") or "",
        schedule=_to_schedule(c),
        source=SOURCE,
    )


def _load_files(campus_codes: list[str]) -> list[str]:
    if campus_codes:
        return [f"scripts/fetched/courses_campus{c}.json" for c in campus_codes]
    return sorted(glob.glob("scripts/fetched/courses_campus*.json"))


async def main():
    files = _load_files(sys.argv[1:])
    if not files:
        print("没找到课程 JSON，先跑 fetch_nju_courses.py 抓取")
        return

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        await db.execute(delete(Course))  # 全量同步：清空重灌
        total = 0
        for path in files:
            courses = json.load(open(path, encoding="utf-8"))
            db.add_all(_to_course(c) for c in courses)
            total += len(courses)
            print(f"{path}: {len(courses)} 门")
        await db.commit()
        print(f"入库 {total} 门课")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
