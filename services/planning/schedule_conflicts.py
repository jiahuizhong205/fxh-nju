"""按教学班时间和校区识别课程冲突。"""


def _int_value(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def detect_schedule_conflicts(
    courses: list[dict],
    user_campus: str = "",
    campus_flexibility: bool = False,
) -> dict:
    """返回时间重叠、校区风险和整体可行性。"""
    slots: list[dict] = []
    warnings: list[str] = []
    for course in courses:
        campus = course.get("campus", "")
        if user_campus and campus and campus != user_campus and not campus_flexibility:
            warnings.append(f"课程 {course.get('name', course.get('id', ''))} 在{campus}，需从{user_campus}通勤")
        for raw in course.get("schedule", []) or []:
            day = _int_value(raw.get("day", raw.get("day_of_week", raw.get("dayOfWeek"))))
            start = _int_value(raw.get("start", raw.get("begin_section", raw.get("beginSection"))))
            end = _int_value(raw.get("end", raw.get("end_section", raw.get("endSection"))))
            if day <= 0 or start <= 0 or end < start:
                continue
            slots.append({
                "course_id": course.get("id", ""),
                "course_name": course.get("name", course.get("course_name", "")),
                "campus": campus,
                "day": day,
                "start": start,
                "end": end,
            })

    conflicts: list[dict] = []
    for index, left in enumerate(slots):
        for right in slots[index + 1:]:
            if left["course_id"] == right["course_id"] or left["day"] != right["day"]:
                continue
            overlap_start = max(left["start"], right["start"])
            overlap_end = min(left["end"], right["end"])
            if overlap_start < overlap_end:
                conflicts.append({
                    "courses": [
                        {"id": left["course_id"], "name": left["course_name"]},
                        {"id": right["course_id"], "name": right["course_name"]},
                    ],
                    "day": left["day"],
                    "start": overlap_start,
                    "end": overlap_end,
                    "message": f"{left['course_name']} 与 {right['course_name']} 在周{left['day']}第{overlap_start}-{overlap_end}节重叠",
                })
    return {
        "conflicts": conflicts,
        "warnings": list(dict.fromkeys(warnings)),
        "feasible": not conflicts,
    }


def build_schedule_options(
    plan_items: list[dict],
    course_offerings: list[dict],
    user_campus: str = "",
) -> dict:
    """为培养方案课程组织实际教学班候选，并优先展示同校区班级。"""
    options_by_name: dict[str, list[dict]] = {}
    for offering in course_offerings:
        options_by_name.setdefault(offering.get("course_name", ""), []).append(offering)

    courses = []
    missing_courses = []
    seen = set()
    for item in plan_items:
        name = item.get("course", "")
        if not name or name in seen:
            continue
        seen.add(name)
        options = sorted(
            options_by_name.get(name, []),
            key=lambda offering: (
                0 if user_campus and offering.get("campus") == user_campus else 1,
                offering.get("school_term", ""),
                offering.get("teaching_class_id", ""),
            ),
        )
        if not options:
            missing_courses.append(name)
        courses.append({
            "course_name": name,
            "required_credits": item.get("credits", 0),
            "offerings": options,
        })
    return {
        "courses": courses,
        "missing_courses": missing_courses,
        "all_available": not missing_courses,
    }
