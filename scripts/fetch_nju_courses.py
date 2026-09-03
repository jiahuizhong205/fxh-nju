"""抓取南大选课系统跨专业(KZY)课程，按校区全量抓取存本地 JSON。

用法:
  NJU_TOKEN=xxx NJU_COOKIE="xxx" python scripts/fetch_nju_courses.py <campus_code>

campus_code: 1=鼓楼 2=仙林 4=苏州（以接口 campusName 为准）
凭证从环境变量读，避免硬编码进代码。
"""

import json
import os
import sys

import httpx

BASE = "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/elective/publicCourse.do"
STUDENT_CODE = "241880299"
BATCH = "e4f378480a6440b1a332dd672c823ee2"

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "language": "zh_cn",
    "Origin": "https://xk.nju.edu.cn",
    "Referer": "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
}


def query_setting(campus: str, page: int) -> dict:
    return {
        "data": {
            "studentCode": STUDENT_CODE,
            "electiveBatchCode": BATCH,
            "teachingClassType": "KZY",
            "campus": campus,
            "checkConflict": "2",
            "checkCapacity": "2",
            "queryContent": "",
        },
        "pageSize": "50",
        "pageNumber": str(page),
        "order": "isChoose -",
    }


def main() -> None:
    campus = sys.argv[1]
    token = os.environ["NJU_TOKEN"]
    cookie = os.environ["NJU_COOKIE"]

    headers = {**HEADERS, "token": token, "Cookie": cookie}

    seen: dict[str, dict] = {}
    page = 0
    while True:
        resp = httpx.post(
            BASE,
            headers=headers,
            data={"querySetting": json.dumps(query_setting(campus, page))},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        lst = data.get("dataList", [])
        if not lst:
            break
        for c in lst:
            seen.setdefault(c["teachingClassID"], c)
        total = data.get("totalCount", 0)
        print(f"page {page}: +{len(lst)} (去重后累计 {len(seen)}/{total})")
        if len(seen) >= total:
            break
        page += 1
        if page > 100:  # 保险，防止死循环
            break

    out = f"scripts/fetched/courses_campus{campus}.json"
    os.makedirs("scripts/fetched", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(list(seen.values()), f, ensure_ascii=False, indent=1)
    print(f"完成：{len(seen)} 门课 → {out}")


if __name__ == "__main__":
    main()
