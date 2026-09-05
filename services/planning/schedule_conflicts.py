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
                1 if offering.get("is_full") else 0,
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


def _offering_score(
    offering: dict,
    user_campus: str,
    time_preferences: list[str],
    conflict_strategies: list[str],
) -> int:
    """为候选教学班打分；分值只用于排序，不代表课程质量。"""
    score = 0
    if offering.get("is_full"):
        score -= 100
    if user_campus and offering.get("campus") == user_campus:
        score += 40

    remote_type = str(offering.get("remote_type", "")).lower()
    if "优先选择线上/混合课程" in conflict_strategies and remote_type in {"online", "hybrid", "线上", "混合"}:
        score += 30

    schedule = offering.get("schedule", []) or []
    sections = [
        _int_value(raw.get("start", raw.get("begin_section", raw.get("beginSection"))))
        for raw in schedule
    ]
    if sections and time_preferences:
        preferred_ranges = []
        if "早八战士" in time_preferences:
            preferred_ranges.append(range(1, 3))
        if "上午黄金档" in time_preferences:
            preferred_ranges.append(range(3, 6))
        if "午后时光" in time_preferences:
            preferred_ranges.append(range(6, 9))
        if "晚间高效派" in time_preferences:
            preferred_ranges.append(range(9, 14))
        if any(section in allowed for section in sections for allowed in preferred_ranges):
            score += 10
    return score


def _schedule_conflict_count(selected: list[dict]) -> int:
    return len(
        detect_schedule_conflicts(
            [
                {
                    "id": item.get("teaching_class_id", ""),
                    "name": item.get("course_name", ""),
                    "campus": item.get("campus", ""),
                    "schedule": item.get("schedule", []) or [],
                }
                for item in selected
            ]
        )["conflicts"]
    )


def auto_select_schedule(
    courses: list[dict],
    user_campus: str = "",
    time_preferences: list[str] | None = None,
    conflict_strategies: list[str] | None = None,
    max_combinations: int = 5000,
) -> dict:
    """从每门课的教学班候选中寻找冲突最少的完整组合。

    这是确定性的本地规划器，不会把满班、缺课或时间冲突隐藏掉；找不到完整可行组合时，
    返回冲突最少的候选并将 ``feasible`` 置为 False，供前端展示人工调整入口。
    """
    time_preferences = time_preferences or []
    conflict_strategies = conflict_strategies or []
    missing_courses = [
        item.get("course_name", "")
        for item in courses
        if not item.get("offerings")
    ]
    available = [item for item in courses if item.get("offerings")]
    ranked = []
    for item in available:
        offerings = sorted(
            item.get("offerings", []),
            key=lambda offering: (
                -_offering_score(offering, user_campus, time_preferences, conflict_strategies),
                offering.get("teaching_class_id", ""),
            ),
        )
        ranked.append((item, offerings))

    combinations: list[tuple[int, int, list[dict], dict]] = []
    visited = 0

    def visit(index: int, selected: list[dict], score: int) -> None:
        nonlocal visited
        if visited >= max_combinations:
            return
        if index == len(ranked):
            visited += 1
            conflicts = _schedule_conflict_count(selected)
            combinations.append((conflicts, -score, list(selected), {}))
            return
        item, offerings = ranked[index]
        for offering in offerings:
            if visited >= max_combinations:
                break
            candidate = {**offering, "course_name": item.get("course_name", offering.get("course_name", ""))}
            visit(index + 1, selected + [candidate], score + _offering_score(
                candidate, user_campus, time_preferences, conflict_strategies
            ))

    visit(0, [], 0)
    if not combinations:
        return {
            "feasible": False,
            "selected_courses": [],
            "selected_teaching_class_ids": [],
            "conflicts": [],
            "warnings": [f"未找到可选教学班：{name}" for name in missing_courses],
            "missing_courses": missing_courses,
            "alternatives": [],
        }

    combinations.sort(key=lambda item: (item[0], item[1], [c.get("teaching_class_id", "") for c in item[2]]))
    best_conflicts, _, selected, _ = combinations[0]
    analysis = detect_schedule_conflicts(
        [
            {
                "id": item.get("teaching_class_id", ""),
                "name": item.get("course_name", ""),
                "campus": item.get("campus", ""),
                "schedule": item.get("schedule", []) or [],
            }
            for item in selected
        ],
        user_campus=user_campus,
        campus_flexibility="跨校区通勤" in conflict_strategies,
    )
    warnings = list(analysis["warnings"])
    warnings.extend(f"未找到可选教学班：{name}" for name in missing_courses)
    if best_conflicts:
        warnings.append("当前组合存在时间冲突，请调整教学班")
    if any(item.get("is_full") for item in selected):
        warnings.append("当前组合包含已满教学班，请尽快向教务确认名额")

    alternatives = []
    seen_ids = set()
    for conflicts, _, option, _ in combinations:
        ids = tuple(item.get("teaching_class_id", "") for item in option)
        if ids in seen_ids:
            continue
        seen_ids.add(ids)
        alternatives.append({
            "teaching_class_ids": list(ids),
            "conflict_count": conflicts,
        })
        if len(alternatives) >= 3:
            break

    return {
        "feasible": not missing_courses and best_conflicts == 0,
        "selected_courses": selected,
        "selected_teaching_class_ids": [item.get("teaching_class_id", "") for item in selected],
        "conflicts": analysis["conflicts"],
        "warnings": list(dict.fromkeys(warnings)),
        "missing_courses": missing_courses,
        "alternatives": alternatives,
    }
