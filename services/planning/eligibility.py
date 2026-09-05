"""专业资格的保守估算。

这里输出的是基于当前已导入培养方案和已修课程的“预估结果”，不是教务处的
正式资格认定。正式认定仍需保留院系审核、成绩门槛和替代课程规则的人工复核。
"""


def _course_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def evaluate_program_eligibility(
    program: dict,
    plan_items: list[dict],
    completed_records: list[dict],
) -> dict:
    """根据已导入数据计算专业资格的可解释估算结果。"""
    required_courses = []
    seen_courses = set()
    for item in plan_items:
        course = _course_name(item.get("course", ""))
        if course and course not in seen_courses:
            required_courses.append(course)
            seen_courses.add(course)

    completed_courses = []
    completed_names = set()
    completed_credits = 0.0
    for record in completed_records:
        if record.get("status", "completed") != "completed":
            continue
        course = _course_name(record.get("course_name", ""))
        if course and course not in completed_names:
            completed_courses.append(course)
            completed_names.add(course)
            completed_credits += float(record.get("credits") or 0)

    missing_courses = [course for course in required_courses if course not in completed_names]
    required_credits = float(program.get("total_credits") or 0)
    plan_credits = sum(float(item.get("credits") or 0) for item in plan_items)
    credit_progress = round(min(completed_credits / required_credits, 1.0), 4) if required_credits else 0.0

    requirements = []
    manual_review_reasons = []
    if program.get("required_math"):
        math_evidence = [
            course for course in completed_courses
            if "高等数学" in course or "高数" in course
        ]
        math_completed = bool(math_evidence)
        requirements.append({
            "type": "math",
            "name": program.get("required_math_level", "高等数学"),
            "completed": math_completed,
            "evidence": math_evidence,
        })
        if not math_completed:
            manual_review_reasons.append("尚未发现满足高数先修要求的已修课程")

    if not plan_items:
        manual_review_reasons.append("当前专业尚未导入可用于判定的培养方案")
    elif plan_credits < required_credits:
        manual_review_reasons.append("已导入培养方案学分不足以覆盖专业总学分，需补充完整方案")
    if missing_courses:
        manual_review_reasons.append(f"尚缺 {len(missing_courses)} 门已导入培养方案课程")

    estimated_eligible = bool(
        plan_items
        and plan_credits >= required_credits
        and completed_credits >= required_credits
        and not missing_courses
        and all(item["completed"] for item in requirements)
    )
    # 即使估算通过，也不能替代南京大学教务/院系的正式认定。
    manual_review_reasons.append("最终资格仍需以教务系统和院系审核为准")

    return {
        "program": program.get("name", ""),
        "estimated_eligible": estimated_eligible,
        "requires_manual_review": True,
        "total_credits": required_credits,
        "plan_credits": plan_credits,
        "completed_credits": completed_credits,
        "credit_progress": credit_progress,
        "required_courses": required_courses,
        "completed_courses": completed_courses,
        "missing_courses": missing_courses,
        "requirements": requirements,
        "manual_review_reasons": manual_review_reasons,
    }
