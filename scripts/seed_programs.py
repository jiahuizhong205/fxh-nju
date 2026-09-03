"""解析培养方案.txt 附件1（专业目录）→ 灌入 programs 表。

用法: PYTHONPATH=. python scripts/seed_programs.py

附件1 三行一组：专业代码 / 专业名称 / 所属院系，中间夹「XX类」分类标签和备注。
附件1 的院系名与选课系统 Course.department 有几处命名差异，用 DEPT_MAP 归一。
学分/校区/排名在附件2（课程体系）里，此处占位 0/""，等解析附件2 再补。
"""

import asyncio
import re
import sys
from collections import Counter

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from apps.api.config import settings
from apps.api.database import Base
from apps.api.models import Program

TXT = "scripts/fetched/培养方案.txt"
# 附件1 在 56..369 行（附件2 从 371 开始）
START, END = 55, 370

# ponytail: 附件1 院系名 → Course.department 标准名（选课系统口径）
DEPT_MAP = {
    "哲学系": "哲学学院",
    "数学系": "数学学院",
    "化学化工学院": "化学学院",
    "计算机科学与技术系": "计算机学院",
}


def parse() -> list[dict]:
    lines = open(TXT, encoding="utf-8").read().split("\n")
    code_re = re.compile(r"^\d{6}[KT]?$")
    dept_re = re.compile(r"^([一-龥]+(?:学院|系))")

    progs: list[dict] = []
    discipline = ""
    for i in range(START, END):
        line = lines[i].strip()
        if not line:
            continue
        if code_re.match(line):
            name = lines[i + 1].strip()
            dept_line = lines[i + 2].strip()
            m = dept_re.match(dept_line)
            raw_dept = m.group(1) if m else dept_line
            progs.append({
                "name": name,
                "discipline": discipline,
                "department": DEPT_MAP.get(raw_dept, raw_dept),
            })
        elif line.endswith("类") and not re.search(r"\d", line) and "不能" not in line and "注意" not in line:
            discipline = line
    return progs


def _to_program(p: dict) -> Program:
    # ponytail: 学分/校区/排名待附件2（课程体系）补充，先占位
    return Program(
        name=p["name"],
        total_credits=0,
        campus="",
        subject_rank="",
        core_courses=[],
        required_math=False,
        required_math_level="",
        semesters_needed=4,
        discipline=p["discipline"],
        department=p["department"],
    )


async def main():
    progs = parse()
    # ponytail: 同一专业可被多个院系开设辅修（如集成电路设计与集成系统），主键撞了加院系后缀区分
    cnt = Counter(p["name"] for p in progs)
    for p in progs:
        if cnt[p["name"]] > 1:
            p["name"] = f"{p['name']}（{p['department']}）"

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(Program))
        db.add_all(_to_program(p) for p in progs)
        await db.commit()
        print(f"入库 {len(progs)} 个辅修专业")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
