"""职业匹配引擎——技能映射 + 岗位匹配 + 简历建议。

ponytail: 模板数据 + 规则匹配，不做实时爬取。实时搜索走 Search Agent (P4)。
"""

# ── 模拟岗位数据 ─────────────────────────────
# 生产环境从 Search Agent 或数据库读取
SAMPLE_JOBS = [
    {
        "id": "job001",
        "employer": "南方周末",
        "title": "实习记者",
        "location": "广州/远程",
        "majors": ["新闻学", "汉语言文学"],
        "preferred_cross": ["中文+新闻", "历史+新闻"],
        "skills_required": ["新闻采写能力", "信息整合与核实", "文字表达能力"],
        "skills_preferred": ["数据分析基础", "多媒体内容制作"],
        "deadline": "2026-09-01",
        "source": "学校就业中心",
    },
    {
        "id": "job002",
        "employer": "字节跳动",
        "title": "内容运营实习生",
        "location": "北京",
        "majors": ["新闻学", "传播学", "汉语言文学"],
        "preferred_cross": ["文学+数据", "新闻+计算机"],
        "skills_required": ["文字表达能力", "信息整合与核实"],
        "skills_preferred": ["数据分析基础", "可视化工具"],
        "deadline": "2026-08-15",
        "source": "企业官网",
    },
    {
        "id": "job003",
        "employer": "澎湃新闻",
        "title": "数据新闻实习生",
        "location": "上海",
        "majors": ["新闻学", "计算机科学与技术"],
        "preferred_cross": ["新闻+计算机", "新闻+统计"],
        "skills_required": ["新闻采写能力", "数据分析基础"],
        "skills_preferred": ["可视化工具", "逻辑论证与批判思维"],
        "deadline": "2026-08-20",
        "source": "学校就业中心",
    },
    {
        "id": "job004",
        "employer": "奥美广告",
        "title": "公关实习生",
        "location": "上海",
        "majors": ["新闻学", "广告学", "市场营销"],
        "preferred_cross": ["文学+传媒", "新闻+市场营销"],
        "skills_required": ["文字表达能力", "信息整合与核实"],
        "skills_preferred": ["多媒体内容制作"],
        "deadline": "2026-09-10",
        "source": "企业官网",
    },
]


CAREER_KEYWORDS = {
    "记者/编辑": ("记者", "编辑"),
    "内容策划/新媒体运营": ("内容", "运营", "策划"),
    "数据新闻记者": ("数据", "记者"),
    "企业传播/公关": ("公关", "传播"),
}


def build_career_outcomes(pathways: list[dict], jobs: list[dict]) -> list[dict]:
    """把技能路径和岗位表汇总为可解释的职业出口画像。"""
    outcomes = []
    for career in sorted({
        name for pathway in pathways for name in pathway.get("careers", [])
    }):
        related_pathways = [
            pathway for pathway in pathways if career in pathway.get("careers", [])
        ]
        skills = sorted({
            pathway.get("skill_name", "")
            for pathway in related_pathways
            if pathway.get("skill_name")
        })
        knowledge_points = sorted({
            point for pathway in related_pathways
            for point in pathway.get("knowledge_points", [])
        })
        keywords = CAREER_KEYWORDS.get(career, ())
        related_jobs = [
            job for job in jobs
            if any(
                skill in (job.get("skills_required", []) + job.get("skills_preferred", []))
                for skill in skills
            ) or any(keyword in job.get("title", "") for keyword in keywords)
        ]
        required_skill_count = len({
            skill for job in related_jobs for skill in job.get("skills_required", [])
        })
        difficulty = "基础"
        if required_skill_count >= 4 or len(skills) >= 3:
            difficulty = "进阶"
        elif required_skill_count >= 2 or len(skills) >= 2:
            difficulty = "中阶"
        outcomes.append({
            "career": career,
            "related_job_count": len(related_jobs),
            "job_titles": sorted({job.get("title", "") for job in related_jobs if job.get("title")}),
            "skills": skills,
            "knowledge_points": knowledge_points,
            "difficulty": difficulty,
            "evidence": "岗位表与知识图谱技能映射",
        })
    return outcomes


def match_jobs(major: str, minor: str | None = None, jobs: list[dict] | None = None) -> list[dict]:
    """按主修+辅修专业匹配岗位，计算技能覆盖度。"""
    jobs = jobs or SAMPLE_JOBS
    results = []
    for job in jobs:
        score = 0
        reasons = []

        # 主修匹配
        if major in job["majors"]:
            score += 30
            reasons.append(f"主修{major}符合要求")

        # 辅修/复合背景加分——宽松匹配
        if minor:
            for pref in job.get("preferred_cross", []):
                minor_short = minor.rstrip("学")  # "新闻学" → "新闻"
                major_short = major.split("专业")[0]
                if minor_short in pref or minor in pref or major_short in pref:
                    score += 25
                    reasons.append(f"复合背景({major}+{minor})为优先考虑")
                    break

        # 技能粗略匹配
        # ponytail: 不做 NLP 语义匹配，关键词即可
        for skill in job.get("skills_required", []):
            score += 10
        score += len(job.get("skills_preferred", [])) * 5

        results.append({
            "job": job,
            "match_score": min(score, 100),
            "match_reasons": reasons,
        })

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results
