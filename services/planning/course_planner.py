"""课程规划引擎——约束满足 + 负载均衡。

ponytail: 贪心+回溯求解，不做 OR-Tools 集成。OR-Tools 产线化时再上。
"""

from dataclasses import dataclass, field
from copy import deepcopy


# ── 辅修培养方案模板 ────────────────────────
# 生产环境从 ProgramRequirement + CourseOffering 读取
PROGRAM_PLANS: dict[str, list[dict]] = {
    "新闻学": [
        {"semester": 1, "term": "秋季", "course": "新闻采访与写作", "credits": 3, "campus": "仙林校区"},
        {"semester": 1, "term": "秋季", "course": "传播学概论", "credits": 3, "campus": "仙林校区"},
        {"semester": 2, "term": "春季", "course": "新闻编辑学", "credits": 3, "campus": "仙林校区"},
        {"semester": 2, "term": "春季", "course": "媒介伦理与法规", "credits": 2, "campus": "仙林校区"},
        {"semester": 3, "term": "秋季", "course": "数据新闻", "credits": 3, "campus": "仙林校区"},
        {"semester": 4, "term": "春季", "course": "新闻评论", "credits": 2, "campus": "仙林校区"},
    ],
    "法学": [
        {"semester": 1, "term": "秋季", "course": "法理学", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 1, "term": "秋季", "course": "宪法学", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 2, "term": "春季", "course": "民法学", "credits": 4, "campus": "鼓楼校区"},
        {"semester": 2, "term": "春季", "course": "刑法学", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 3, "term": "秋季", "course": "行政法学", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 3, "term": "秋季", "course": "经济法学", "credits": 3, "campus": "鼓楼校区"},
    ],
    "计算机科学与技术": [
        {"semester": 1, "term": "秋季", "course": "程序设计基础", "credits": 3, "campus": "仙林校区"},
        {"semester": 1, "term": "秋季", "course": "数据结构", "credits": 4, "campus": "仙林校区"},
        {"semester": 2, "term": "春季", "course": "计算机系统基础", "credits": 4, "campus": "仙林校区"},
        {"semester": 2, "term": "春季", "course": "数据库概论", "credits": 3, "campus": "仙林校区"},
        {"semester": 3, "term": "秋季", "course": "计算机网络", "credits": 3, "campus": "仙林校区"},
    ],
    "金融学": [
        {"semester": 1, "term": "秋季", "course": "微观经济学", "credits": 3, "campus": "仙林校区"},
        {"semester": 1, "term": "秋季", "course": "宏观经济学", "credits": 3, "campus": "仙林校区"},
        {"semester": 2, "term": "春季", "course": "会计学", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 2, "term": "春季", "course": "公司金融", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 3, "term": "秋季", "course": "投资学", "credits": 3, "campus": "鼓楼校区"},
        {"semester": 3, "term": "秋季", "course": "金融市场学", "credits": 3, "campus": "鼓楼校区"},
    ],
}


@dataclass
class PlanItem:
    semester: int
    term: str
    year: int
    course: str
    credits: int
    campus: str


@dataclass
class PlanResult:
    program_name: str
    items: list[PlanItem] = field(default_factory=list)
    alternatives: list[list[PlanItem]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infeasible: bool = False


def generate_plan(program_name: str, profile: dict, plans: dict | None = None) -> PlanResult:
    """生成课程规划——贪心分配 + 约束检查。"""
    plans = plans or PROGRAM_PLANS
    courses = plans.get(program_name, [])
    if not courses:
        return PlanResult(program_name=program_name, infeasible=True, warnings=[f"未找到{program_name}的培养方案"])

    grade = profile.get("grade", "大二")
    grade_to_start = {"大一": 1, "大二": 3, "大三": 5, "大四": 7}
    start_semester = grade_to_start.get(grade, 3)
    user_campus = profile.get("campus", "")
    campus_ok = profile.get("campus_flexibility", False)
    prefer_late = profile.get("schedule_preferences", {}).get("prefer_late", False)

    items: list[PlanItem] = []
    warnings: list[str] = []

    # 贪心分配：从 start_semester 开始
    for course in courses:
        offset = course["semester"] - 1  # 0-indexed
        assigned_sem = start_semester + offset

        # 偏好：推迟辅修课程
        if prefer_late:
            assigned_sem += 2

        # 避免超载（每学期辅修不超过 8 学分）
        term_credits = sum(it.credits for it in items if it.semester == assigned_sem)
        if term_credits + course["credits"] > 8:
            assigned_sem += 1
            if assigned_sem > 12:
                warnings.append(f"课程 {course['course']} 无法在不超载的情况下排入")

        year = (assigned_sem + 1) // 2
        term = "秋季" if assigned_sem % 2 == 1 else "春季"

        item = PlanItem(
            semester=assigned_sem,
            term=term,
            year=year,
            course=course["course"],
            credits=course["credits"],
            campus=course["campus"],
        )
        items.append(item)

        # 校区检查
        if not campus_ok and user_campus and course["campus"] != user_campus:
            if "苏州" in course["campus"] or "苏州" in user_campus:
                warnings.append(f"课程 {course['course']} 在{course['campus']}，与{user_campus}不可通勤")
            else:
                warnings.append(f"课程 {course['course']} 在{course['campus']}，需跨校区通勤（{user_campus}）")

    # 生成备选方案——推迟一学期
    alt = deepcopy(items)
    for it in alt:
        it.semester += 1
        it.year = (it.semester + 1) // 2
        it.term = "秋季" if it.semester % 2 == 1 else "春季"

    total_credits = sum(it.credits for it in items)
    return PlanResult(
        program_name=program_name,
        items=items,
        alternatives=[alt],
        warnings=warnings,
        infeasible=len(warnings) > 2,
    )
