import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfficialMinorDataTests(unittest.TestCase):
    def test_parser_keeps_official_course_fields_and_allocates_terms(self):
        from scripts.sync_official_minor_data import parse_pages

        pages = ["""南京大学 2025 版本科辅修专业培养方案
文学院
汉语言文学专业本科辅修课程体系
课程类别 课程号 课程名称 学分 开课学期 备注
专业核心课程
01000010A 中国古代文学 3 秋季
01000010B 中国古代文学 3 春季
辅修学位论文 01032490S 汉语言文学专业辅修学位论文 2 春季
学分总计： 8
"""]

        programs = parse_pages(pages)
        self.assertEqual(len(programs), 1)
        program = programs[0]
        self.assertEqual(program["name"], "汉语言文学")
        self.assertEqual(program["department"], "文学院")
        self.assertEqual(program["total_credits"], 8)
        self.assertTrue(program["plan_complete"])
        self.assertEqual(program["courses"][0]["course_code"], "01000010A")
        self.assertEqual(program["courses"][0]["category"], "专业核心课程")
        self.assertEqual(program["courses"][0]["official_term"], "秋季")
        self.assertEqual(program["courses"][2]["category"], "辅修学位论文")

    def test_api_does_not_fall_back_to_demo_programs_or_jobs(self):
        planning = (ROOT / "apps/api/routes/planning.py").read_text(encoding="utf-8")
        self.assertNotIn("SAMPLE_JOBS", planning)
        self.assertNotIn("PROGRAM_PLANS", planning)

    def test_empty_explicit_inputs_do_not_activate_demo_data(self):
        from services.planning.career_engine import match_jobs
        from services.planning.course_planner import generate_plan
        from services.planning.recommendation_engine import recommend

        self.assertEqual(match_jobs("新闻学", jobs=[]), [])
        self.assertEqual(recommend({"major": "新闻学"}, programs=[]), [])
        self.assertTrue(generate_plan("新闻学", {}, plans={}).infeasible)


if __name__ == "__main__":
    unittest.main()
