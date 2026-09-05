"""轻量级、可追踪的 PostgreSQL SQL 迁移运行器。"""

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "infra" / "migrations"


def discover_migrations() -> list[Path]:
    """按文件名返回编号迁移，避免依赖操作系统目录顺序。"""
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"), key=lambda path: path.name)


def split_sql_statements(sql: str) -> list[str]:
    """按分号拆分 SQL，同时保留字符串字面量中的分号。"""
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0

    while index < len(sql):
        character = sql[index]

        if character == "-" and index + 1 < len(sql) and sql[index + 1] == "-":
            while index < len(sql) and sql[index] not in "\r\n":
                index += 1
            continue

        if character == "'" and not in_double_quote:
            current.append(character)
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                current.append(sql[index + 1])
                index += 2
                continue
            in_single_quote = not in_single_quote
        elif character == '"' and not in_single_quote:
            current.append(character)
            if in_double_quote and index + 1 < len(sql) and sql[index + 1] == '"':
                current.append(sql[index + 1])
                index += 2
                continue
            in_double_quote = not in_double_quote
        elif character == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(character)
        index += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


async def apply_migrations(conn: AsyncConnection) -> list[str]:
    """原子地执行尚未记录的迁移，并返回本次新应用的文件名。"""
    if conn.dialect.name != "postgresql":
        return []

    await conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version VARCHAR(255) PRIMARY KEY, "
        "applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    ))
    result = await conn.execute(text("SELECT version FROM schema_migrations"))
    applied = set(result.scalars().all())
    completed: list[str] = []

    for path in discover_migrations():
        if path.name in applied:
            continue
        for statement in split_sql_statements(path.read_text(encoding="utf-8")):
            await conn.execute(text(statement))
        await conn.execute(
            text("INSERT INTO schema_migrations(version) VALUES (:version)"),
            {"version": path.name},
        )
        completed.append(path.name)

    return completed
