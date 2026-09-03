"""解析培养方案.txt 附件2（课程体系）→ 补全 programs 表的学分与核心课程。

用法: PYTHONPATH=. python scripts/seed_program_details.py

附件2 每专业一块：标题「XX专业本科辅修课程体系」+ 课程表（课程类别/课程号/课程名/学分）。
补 Program.total_credits = 学分总计；Program.core_courses = 专业核心课程名（去重保序）。
前提：先跑 seed_programs.py 建好专业目录（本脚本按 name 匹配 UPDATE）。
"""

import asyncio
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from apps.api.config import settings
from apps.api.models import Program

TXT = "scripts/fetched/培养方案.txt"

# ponytail: 附件2 院系名 → Program.department 标准名（选课系统口径）
DEPT_MAP = {"化学化工学院": "化学学院"}
# ponytail: 附件2 专业名 → 附件1（Program.name）口径，同一专业在目录/课程体系里书写不一致
NAME_MAP = {
    "应用物理": "应用物理学",
    "水文与水资源": "水文与水资源工程",
    "微电子科学与技术": "微电子科学与工程",
    "城乡规划学": "城乡规划",
}

CATS = {"专业核心课程", "专业选修课程", "学科基础课程", "专业课程",
        "实践类课程", "项目制课程", "辅修学位论文"}
code_re = re.compile(r"^\d{8}[A-Za-z]?$")
credit_re = re.compile(r"^\d{1,2}$")
total_re = re.compile(r"(学分总计|总学分)[:：]?\s*(\d+)")


def _norm_dept(d: str) -> str:
    d = d.replace("学院学院", "学院")  # PDF 提取误差
    return DEPT_MAP.get(d, d)


def _dept_of(lines: list[str], start: int) -> str:
    for j in range(start - 1, max(start - 7, -1), -1):
        t = lines[j].strip()
        if not t:
            continue
        if "南京大学" in t or "培养方案" in t or "课程体系" in t or "课程" in t:
            continue
        if "学院" in t or t.endswith("系"):
            return _norm_dept(t)
    return ""


def parse() -> list[dict]:
    lines = open(TXT, encoding="utf-8").read().split("\n")
    anchors = [i for i, l in enumerate(lines) if "本科辅修课程体系" in l]

    progs: list[dict] = []
    for idx, start in enumerate(anchors):
        end = anchors[idx + 1] if idx + 1 < len(anchors) else len(lines)
        raw_name = lines[start].strip().replace("专业本科辅修课程体系", "").replace("本科辅修课程体系", "").strip()
        raw_name = NAME_MAP.get(raw_name, raw_name)
        dept = _dept_of(lines, start)
        total = None
        core: list[str] = []
        cur = ""
        i = start
        while i < end:
            s = lines[i].strip()
            m = total_re.search(s)
            if m and total is None:
                total = int(m.group(2))
            if s in CATS:
                cur = s
            elif cur == "专业核心课程" and code_re.match(s):
                # 课程名 = 课程号后连续非数字行拼接（PDF 换行会拆课程名），直到学分行
                parts: list[str] = []
                j = i + 1
                while j < end:
                    t = lines[j].strip()
                    if credit_re.match(t):
                        break
                    if t and t not in CATS and not code_re.match(t):
                        parts.append(t)
                    j += 1
                core.append("".join(parts))
            i += 1
        progs.append({"name": raw_name, "department": dept, "total_credits": total, "core": core})

    # 重名专业加院系后缀（与 seed_programs.py 同规则）
    cnt = Counter(p["name"] for p in progs)
    for p in progs:
        if cnt[p["name"]] > 1:
            p["name"] = f"{p['name']}（{p['department']}）"
        p["core"] = list(dict.fromkeys(p["core"]))  # 去重保序（同名不同班只留一门）
    return progs


async def main():
    progs = parse()
    # 校验：学分与核心课程都解析到了
    bad = [p["name"] for p in progs if p["total_credits"] is None or not p["core"]]
    if bad:
        print(f"解析不完整 {len(bad)} 个专业，中止: {bad}")
        return

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        names = {p["name"] for p in progs}
        exist = set((await db.execute(select(Program.name))).scalars().all())
        missing = names - exist
        if missing:
            print(f"以下专业不在 programs 表（先跑 seed_programs.py）: {missing}")
            return
        for p in progs:
            prog = await db.get(Program, p["name"])
            prog.total_credits = p["total_credits"]
            prog.core_courses = p["core"]
        await db.commit()
        print(f"补全 {len(progs)} 个专业的学分与核心课程")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
