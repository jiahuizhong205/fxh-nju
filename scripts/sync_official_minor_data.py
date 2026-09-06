"""同步南京大学 2025 版本科辅修目录、课程体系与政策正文。

默认从南京大学本科生院官网下载 PDF；也可用 ``--pdf`` 指向已下载文件。
课程表只有在课程学分合计与官方总学分一致时才写入自动规划表，避免把
带有选修约束的候选课程池误当成全部必修课程。
"""

from __future__ import annotations

import argparse
import asyncio
import re
import tempfile
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.database import Base
from apps.api.models import Document, Program, ProgramPlanItem
from services.rag.ingestion import ingest_document


TITLE = "南京大学2025版本科辅修专业培养方案"
CATALOG_VERSION = "2025"
SOURCE_URL = "https://jw.nju.edu.cn/_upload/article/files/63/bc/95d64cf74027959b18a5e098ebd4/d91cf340-12d8-40ab-bc98-abfa8474011a.pdf"
HEADING_RE = re.compile(r"^(.+?)专业本科辅修课程体系\s*$")
TOTAL_RE = re.compile(r"学分总计[：:]?[^\d]{0,12}(\d+)")
COURSE_RE = re.compile(
    r"(?:^|\s)(\d{6,9}[A-Za-z]*|（新建）|新建)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+(春季|秋季|春秋季)\s*(?:.*)?$"
)
CATEGORIES = {
    "学科基础课程", "专业核心课程", "专业课程", "专业选修课程", "实践类课程",
    "项目制课程", "辅修学位论文", "学位论文",
}


def _department(lines: list[str], heading_index: int) -> str:
    for line in reversed(lines[:heading_index]):
        value = line.strip()
        if value and value != "附件 2：" and "南京大学" not in value:
            return value
    return ""


def _allocate_semesters(courses: list[dict]) -> None:
    loads: dict[int, float] = {}
    for course in courses:
        allowed = (1, 3, 5, 7) if course["official_term"] == "秋季" else (2, 4, 6, 8)
        if course["official_term"] == "春秋季":
            allowed = tuple(range(1, 9))
        semester = next((s for s in allowed if loads.get(s, 0) + course["credits"] <= 8), allowed[-1])
        loads[semester] = loads.get(semester, 0) + course["credits"]
        course["semester"] = semester
        course["term"] = "秋季" if semester % 2 else "春季"


def parse_pages(pages: list[str]) -> list[dict]:
    programs: list[dict] = []
    lines = [line.strip() for page in pages for line in page.splitlines() if line.strip()]
    headings = [(index, HEADING_RE.match(line)) for index, line in enumerate(lines) if HEADING_RE.match(line)]
    for heading_number, (heading_index, match) in enumerate(headings):
        end_index = headings[heading_number + 1][0] if heading_number + 1 < len(headings) else len(lines)
        block_lines = lines[heading_index:end_index]
        block = "\n".join(block_lines)
        current_category = ""
        courses: list[dict] = []
        total_match = TOTAL_RE.search(block)
        if not total_match:
            raise ValueError(f"{match.group(1)}未解析到学分总计")
        for line in block_lines[1:]:
            if line in CATEGORIES:
                current_category = line
                continue
            course_match = COURSE_RE.search(line)
            if not course_match:
                continue
            prefix = line[:course_match.start()].strip()
            if prefix in CATEGORIES:
                current_category = prefix
            credits = float(course_match.group(3))
            courses.append({
                "course_code": course_match.group(1),
                "course": course_match.group(2).strip(),
                "credits": int(credits) if credits.is_integer() else credits,
                "official_term": course_match.group(4),
                "category": current_category,
            })
        if not courses:
            raise ValueError(f"{match.group(1)}未解析到课程")
        total_credits = int(total_match.group(1))
        plan_complete = sum(float(course["credits"]) for course in courses) == total_credits
        if plan_complete:
            _allocate_semesters(courses)
        programs.append({
            "name": match.group(1).strip(),
            "department": _department(lines, heading_index),
            "total_credits": total_credits,
            "core_courses": list(dict.fromkeys(c["course"] for c in courses if "核心" in c["category"])),
            "courses": courses,
            "plan_complete": plan_complete,
        })

    counts = Counter(program["name"] for program in programs)
    for program in programs:
        if counts[program["name"]] > 1:
            program["name"] = f"{program['name']}（{program['department']}）"
    return programs


def extract_pdf(path: Path) -> tuple[list[dict], str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    programs = parse_pages(pages)
    if len(programs) < 70:
        raise ValueError(f"只解析到 {len(programs)} 个专业，拒绝同步不完整数据")
    return programs, "\n\n".join(pages)


async def sync_database(programs: list[dict], content: str) -> dict:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(update(Program).values(is_active=False))
        synced_names: list[str] = []
        for parsed in programs:
            program = await db.get(Program, parsed["name"])
            if program is None:
                program = Program(
                    name=parsed["name"], total_credits=parsed["total_credits"], campus="",
                    subject_rank="", core_courses=[], required_math=False,
                    required_math_level="", semesters_needed=4, discipline="", department="",
                )
                db.add(program)
            program.total_credits = parsed["total_credits"]
            program.core_courses = parsed["core_courses"]
            program.department = parsed["department"]
            if not program.discipline:
                program.discipline = parsed["department"]
            if parsed["plan_complete"]:
                program.semesters_needed = max(course["semester"] for course in parsed["courses"])
            program.catalog_version = CATALOG_VERSION
            program.source_url = SOURCE_URL
            program.is_active = True
            synced_names.append(program.name)
        await db.flush()
        await db.execute(delete(ProgramPlanItem).where(ProgramPlanItem.program_name.in_(synced_names)))
        plan_count = 0
        for parsed in programs:
            if not parsed["plan_complete"]:
                continue
            for course in parsed["courses"]:
                db.add(ProgramPlanItem(
                    program_name=parsed["name"], semester=course["semester"], term=course["term"],
                    course=course["course"], credits=course["credits"], campus="",
                    course_code=course["course_code"], category=course["category"],
                    official_term=course["official_term"], source_url=SOURCE_URL,
                ))
                plan_count += 1
        await db.commit()

        existing = (await db.execute(select(Document).where(Document.source_url == SOURCE_URL))).scalar_one_or_none()
        if not existing:
            await ingest_document(
                db, title=TITLE, content=content, trust_level="S", source_type="policy",
                valid_from=datetime(2025, 9, 1), source_url=SOURCE_URL,
            )
        result = {
            "programs": len(programs),
            "structured_programs": sum(1 for p in programs if p["plan_complete"]),
            "plan_items": plan_count,
        }
    await engine.dispose()
    return result


async def main(pdf_path: str = "", validate_only: bool = False) -> None:
    temporary_path: Path | None = None
    try:
        if pdf_path:
            path = Path(pdf_path)
        else:
            handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            handle.close()
            temporary_path = Path(handle.name)
            urllib.request.urlretrieve(SOURCE_URL, temporary_path)
            path = temporary_path
        programs, content = extract_pdf(path)
        valid = sum(1 for program in programs if program["plan_complete"])
        print(f"解析专业 {len(programs)} 个，可无歧义结构化 {valid} 个")
        if not validate_only:
            print(await sync_database(programs, content))
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.pdf, args.validate_only))
