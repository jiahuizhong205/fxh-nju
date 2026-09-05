"""辅修推荐引擎——硬门槛过滤 + 多指标评分。

ponytail: 规则硬编码，不做可配化。数据变化时直接改代码。
"""

from dataclasses import dataclass, field

# ── 辅修专业数据 ──────────────────────────────
# 生产环境应从数据库 Program/ProgramRequirement 读取
PROGRAMS: list[dict] = [
    {
        "name": "新闻学",
        "total_credits": 45,
        "campus": "仙林校区",
        "subject_rank": "A",
        "core_courses": [
            "新闻采访与写作", "传播学概论", "新闻编辑学",
            "媒介伦理与法规", "数据新闻", "新闻评论",
        ],
        "required_math": False,
        "required_math_level": "",
        "semesters_needed": 4,
        "discipline": "文学",
        "department": "新闻传播学院",
    },
    {
        "name": "法学",
        "total_credits": 50,
        "campus": "鼓楼校区",
        "subject_rank": "A-",
        "core_courses": [
            "法理学", "宪法学", "民法学", "刑法学", "行政法学", "经济法学",
        ],
        "required_math": False,
        "required_math_level": "",
        "semesters_needed": 5,
        "discipline": "法学",
        "department": "法学院",
    },
    {
        "name": "计算机科学与技术",
        "total_credits": 55,
        "campus": "仙林校区",
        "subject_rank": "A+",
        "core_courses": [
            "程序设计基础", "数据结构", "计算机系统基础",
            "数据库概论", "计算机网络",
        ],
        "required_math": True,
        "required_math_level": "高等数学（一）或高等数学（二）",
        "semesters_needed": 5,
        "discipline": "工学",
        "department": "计算机学院",
    },
    {
        "name": "金融学",
        "total_credits": 48,
        "campus": "仙林校区",
        "subject_rank": "A",
        "core_courses": [
            "微观经济学", "宏观经济学", "会计学",
            "公司金融", "投资学", "金融市场学",
        ],
        "required_math": True,
        "required_math_level": "高等数学（一）",
        "semesters_needed": 5,
        "discipline": "经济学",
        "department": "商学院",
    },
]


@dataclass
class FilterResult:
    program_name: str
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    program_name: str
    scores: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    risk_items: list[str] = field(default_factory=list)


def hard_filter(program: dict, profile: dict) -> FilterResult:
    """硬门槛过滤：不满足即排除。"""
    reasons = []

    # 校区不可行
    prog_campus = program["campus"]
    user_campus = profile.get("campus", "")
    campus_ok = profile.get("campus_flexibility", False)
    if not campus_ok and user_campus and prog_campus != user_campus:
        # 检查是否可通勤（仙林↔鼓楼可，苏州不可）
        if "苏州" in prog_campus or "苏州" in user_campus:
            reasons.append(f"{prog_campus}与{user_campus}不可通勤")

    # 数学门槛：已修并通过高数时，不再要求用户重新确认愿修意愿。
    completed_courses = profile.get("completed_courses", [])
    math_completed = any("高等数学" in course or "高数" in course for course in completed_courses)
    if program.get("required_math") and not profile.get("math_willingness", False) and not math_completed:
        certificate = profile.get("certificate_goal", "")
        if certificate == "degree":
            reasons.append(f"需要修读{program['required_math_level']}，但用户不接受修高数")
        elif certificate == "cert":
            pass  # 不追求学位的可修但不能拿学位
        elif not certificate:
            reasons.append(f"建议确认是否愿修{program['required_math_level']}，否则最多拿结业证明")

    # 剩余学期不足
    grade = profile.get("grade", "")
    semesters_remaining = {"大一": 8, "大二": 6, "大三": 4, "大四": 2}.get(grade, 0)
    if semesters_remaining < program.get("semesters_needed", 4):
        reasons.append(f"剩余{semesters_remaining}学期不足以完成{program['semesters_needed']}学期辅修")

    # 学分预算不足
    budget = profile.get("credit_budget", 0)
    if budget > 0 and budget < program["total_credits"]:
        reasons.append(f"用户预算{budget}学分不足以完成{program['total_credits']}学分")

    return FilterResult(
        program_name=program["name"],
        passed=len([r for r in reasons if "不可通勤" in r or "剩余" in r or "不足" in r]) == 0,
        reasons=reasons,
    )


def score_program(program: dict, profile: dict) -> ScoreResult:
    """多指标评分——weighted sum of normalized sub-scores."""
    scores = {}
    risks = []

    # interest_fit (0.25) — 基于兴趣关键词匹配
    interests = " ".join(profile.get("interests", [])).lower()
    prog_text = f"{program['name']} {program['discipline']} {' '.join(program['core_courses'][:4])}".lower()
    interest_hit = any(word in prog_text for word in interests.split()) if interests else 0.5
    scores["interest_fit"] = 0.7 if interest_hit else 0.3
    if not interests:
        scores["interest_fit"] = 0.5  # 未填则中性

    # career_fit (0.20) — 基于职业目标关键词
    career = profile.get("career_goals", "").lower()
    discipline_map = {
        "新闻学": ["传媒", "文化", "媒体", "编辑", "记者", "新闻", "广告"],
        "法学": ["法律", "律师", "法务", "公务员"],
        "计算机科学与技术": ["互联网", "程序员", "开发", "数据", "AI", "产品"],
        "金融学": ["金融", "投资", "银行", "证券", "基金", "经济", "咨询"],
    }
    career_keywords = discipline_map.get(program["name"], [])
    career_hit = any(kw in career for kw in career_keywords) if career else False
    scores["career_fit"] = 0.7 if career_hit else 0.3
    if not career:
        scores["career_fit"] = 0.5

    # prerequisite_readiness (0.20) — 文科生选理科扣分
    arts_majors = ["文学", "历史", "哲学", "外语", "新闻", "中文", "汉语言", "社会学"]
    is_arts = any(m in profile.get("major", "") for m in arts_majors)
    completed_courses = profile.get("completed_courses", [])
    math_completed = any("高等数学" in course or "高数" in course for course in completed_courses)
    if program.get("required_math") and math_completed:
        scores["prerequisite_readiness"] = 0.9
    elif program.get("required_math") and is_arts:
        scores["prerequisite_readiness"] = 0.2
        risks.append(f"文科跨理科辅修，前置知识差距大")
    elif program.get("required_math") and not is_arts:
        scores["prerequisite_readiness"] = 0.6
    else:
        scores["prerequisite_readiness"] = 0.8

    # schedule_feasibility (0.15) — 课程多分配罚分
    scores["schedule_feasibility"] = max(0.3, 1.0 - program["total_credits"] / 120)

    # campus_feasibility (0.10)
    if "苏州" in program["campus"]:
        scores["campus_feasibility"] = 0.1
    elif program["campus"] != profile.get("campus", "") and not profile.get("campus_flexibility"):
        scores["campus_feasibility"] = 0.4
    else:
        scores["campus_feasibility"] = 0.8

    # weighted sum
    # ponytail: overlap_efficiency（与主修课程重合度）依赖各院系自身培养方案数据，暂缺，不参与评分。
    # 其余 5 项按原比例归一化到 1.0。
    weights = {
        "interest_fit": 0.28, "career_fit": 0.22,
        "prerequisite_readiness": 0.22, "schedule_feasibility": 0.17,
        "campus_feasibility": 0.11,
    }
    total = sum(scores[k] * weights.get(k, 0) for k in scores)

    return ScoreResult(
        program_name=program["name"],
        scores=scores,
        total=round(total, 3),
        risk_items=risks,
    )


def _build_explanation(program: dict, profile: dict, scores: dict, filter_reasons: list[str]) -> list[str]:
    """把评分规则转换成可展示、可追溯的解释。"""
    explanations = []
    if scores.get("interest_fit", 0) >= 0.7:
        explanations.append("与你填写的兴趣方向匹配")
    elif scores.get("interest_fit", 0) <= 0.3:
        explanations.append("当前兴趣方向与该专业匹配较弱")
    if scores.get("career_fit", 0) >= 0.7:
        explanations.append("与你填写的职业目标匹配")
    if profile.get("completed_courses") and scores.get("prerequisite_readiness", 0) >= 0.8:
        explanations.append("已修课程为部分先修判断提供支持")
    if scores.get("campus_feasibility", 0) >= 0.8:
        explanations.append("校区安排与当前偏好较适配")
    explanations.extend(f"注意：{reason}" for reason in filter_reasons)
    return explanations or ["根据当前画像的综合评分生成"]


def recommend(profile: dict, programs: list[dict] | None = None) -> list[dict]:
    """执行硬过滤 + 评分排序，返回 Top-N 推荐。"""
    programs = programs or PROGRAMS
    results = []
    for prog in programs:
        filt = hard_filter(prog, profile)
        if not filt.passed:
            continue
        scored = score_program(prog, profile)
        results.append({
            "program": prog,
            "scores": scored.scores,
            "total_score": scored.total,
            "risks": scored.risk_items + [r for r in filt.reasons if "建议" in r],
            "explanation": _build_explanation(prog, profile, scored.scores, filt.reasons),
        })

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results
