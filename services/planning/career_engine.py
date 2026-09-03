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
