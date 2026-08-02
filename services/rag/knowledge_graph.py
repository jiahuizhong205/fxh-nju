"""知识图谱——PostgreSQL 递归 CTE 实现。

ponytail: 单表存节点+边，递归 CTE 做先修查询，不引入 Neo4j。
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class GraphNode:
    id: str
    label: str  # Program / Course / KnowledgePoint / Skill / CareerPath
    name: str
    properties: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str  # REQUIRES / TEACHES / MAPS_TO_SKILL / MATCHES_CAREER / BELONGS_TO


# ── 新闻学辅修知识图谱（种子数据） ──────────────
# 生产环境从 DB 读取

NEWS_GRAPH: dict[str, list] = {
    "nodes": [
        # 课程
        GraphNode("c001", "Course", "新闻采访与写作", {"credits": 3, "semester": 1}),
        GraphNode("c002", "Course", "传播学概论", {"credits": 3, "semester": 1}),
        GraphNode("c003", "Course", "新闻编辑学", {"credits": 3, "semester": 2}),
        GraphNode("c004", "Course", "媒介伦理与法规", {"credits": 2, "semester": 2}),
        GraphNode("c005", "Course", "数据新闻", {"credits": 3, "semester": 3}),
        GraphNode("c006", "Course", "新闻评论", {"credits": 2, "semester": 4}),
        # 知识点
        GraphNode("k001", "KnowledgePoint", "新闻价值判断",
                  {"difficulty": 1, "category": "采写基础"}),
        GraphNode("k002", "KnowledgePoint", "采访技巧与提问策略",
                  {"difficulty": 1, "category": "采写基础"}),
        GraphNode("k003", "KnowledgePoint", "消息与通讯写作",
                  {"difficulty": 2, "category": "采写基础"}),
        GraphNode("k004", "KnowledgePoint", "传播模式与效果理论",
                  {"difficulty": 2, "category": "传播理论"}),
        GraphNode("k005", "KnowledgePoint", "媒介发展史与媒介社会学",
                  {"difficulty": 2, "category": "传播理论"}),
        GraphNode("k006", "KnowledgePoint", "新闻编辑流程与版面设计",
                  {"difficulty": 2, "category": "编辑实务"}),
        GraphNode("k007", "KnowledgePoint", "标题制作与稿件修改",
                  {"difficulty": 2, "category": "编辑实务"}),
        GraphNode("k008", "KnowledgePoint", "新闻法律与伦理准则",
                  {"difficulty": 1, "category": "伦理法规"}),
        GraphNode("k009", "KnowledgePoint", "数据采集与清洗",
                  {"difficulty": 3, "category": "数据新闻"}),
        GraphNode("k010", "KnowledgePoint", "数据可视化工具",
                  {"difficulty": 3, "category": "数据新闻"}),
        GraphNode("k011", "KnowledgePoint", "评论选题与论点构建",
                  {"difficulty": 3, "category": "新闻评论"}),
        GraphNode("k012", "KnowledgePoint", "深度报道与非虚构写作",
                  {"difficulty": 4, "category": "进阶写作"}),
        # 技能
        GraphNode("s001", "Skill", "新闻采写能力"),
        GraphNode("s002", "Skill", "信息整合与核实"),
        GraphNode("s003", "Skill", "文字表达能力"),
        GraphNode("s004", "Skill", "数据分析基础"),
        GraphNode("s005", "Skill", "可视化工具(Flourish/Datawrapper)"),
        GraphNode("s006", "Skill", "逻辑论证与批判思维"),
        GraphNode("s007", "Skill", "多媒体内容制作"),
        # 职业方向
        GraphNode("j001", "CareerPath", "记者/编辑", {"industry": "新闻传媒"}),
        GraphNode("j002", "CareerPath", "内容策划/新媒体运营", {"industry": "互联网/文化传媒"}),
        GraphNode("j003", "CareerPath", "数据新闻记者", {"industry": "数据新闻/科技媒体"}),
        GraphNode("j004", "CareerPath", "企业传播/公关", {"industry": "企业/公关"}),
    ],
    "edges": [
        # 课程→知识点
        GraphEdge("c001", "k001", "TEACHES"),
        GraphEdge("c001", "k002", "TEACHES"),
        GraphEdge("c001", "k003", "TEACHES"),
        GraphEdge("c002", "k004", "TEACHES"),
        GraphEdge("c002", "k005", "TEACHES"),
        GraphEdge("c003", "k006", "TEACHES"),
        GraphEdge("c003", "k007", "TEACHES"),
        GraphEdge("c004", "k008", "TEACHES"),
        GraphEdge("c005", "k009", "TEACHES"),
        GraphEdge("c005", "k010", "TEACHES"),
        GraphEdge("c006", "k011", "TEACHES"),
        # 先修关系
        GraphEdge("k001", "k003", "REQUIRES"),
        GraphEdge("k002", "k003", "REQUIRES"),
        GraphEdge("k001", "k011", "REQUIRES"),
        GraphEdge("k006", "k011", "REQUIRES"),
        GraphEdge("k003", "k012", "REQUIRES"),
        GraphEdge("k009", "k010", "REQUIRES"),
        # 知识点→技能
        GraphEdge("k001", "s001", "MAPS_TO_SKILL"),
        GraphEdge("k002", "s001", "MAPS_TO_SKILL"),
        GraphEdge("k003", "s003", "MAPS_TO_SKILL"),
        GraphEdge("k004", "s002", "MAPS_TO_SKILL"),
        GraphEdge("k009", "s004", "MAPS_TO_SKILL"),
        GraphEdge("k010", "s005", "MAPS_TO_SKILL"),
        GraphEdge("k011", "s006", "MAPS_TO_SKILL"),
        GraphEdge("k012", "s003", "MAPS_TO_SKILL"),
        GraphEdge("k007", "s002", "MAPS_TO_SKILL"),
        # 技能→职业
        GraphEdge("s001", "j001", "MATCHES_CAREER"),
        GraphEdge("s002", "j001", "MATCHES_CAREER"),
        GraphEdge("s003", "j002", "MATCHES_CAREER"),
        GraphEdge("s007", "j002", "MATCHES_CAREER"),
        GraphEdge("s004", "j003", "MATCHES_CAREER"),
        GraphEdge("s005", "j003", "MATCHES_CAREER"),
        GraphEdge("s003", "j004", "MATCHES_CAREER"),
        GraphEdge("s006", "j004", "MATCHES_CAREER"),
    ],
}


def get_knowledge_tree(course_names: list[str]) -> dict:
    """根据课程名生成知识树——BFS 从课程展开知识点+先修链。"""
    courses = [n for n in NEWS_GRAPH["nodes"]
               if n.label == "Course" and n.name in course_names]
    if not courses:
        return {"nodes": [], "edges": []}

    course_ids = {c.id for c in courses}
    # 从课程出发，通过 TEACHES 找到知识点
    kp_ids: set[str] = set()
    for e in NEWS_GRAPH["edges"]:
        if e.relation == "TEACHES" and e.source_id in course_ids:
            kp_ids.add(e.target_id)

    # BFS 通过 REQUIRES 扩展先修知识点
    all_kp_ids = set(kp_ids)
    frontier = list(kp_ids)
    while frontier:
        current = frontier.pop()
        for e in NEWS_GRAPH["edges"]:
            if e.relation == "REQUIRES" and e.target_id == current:
                if e.source_id not in all_kp_ids:
                    all_kp_ids.add(e.source_id)
                    frontier.append(e.source_id)

    # 收集所有相关节点和边
    node_map = {}
    all_ids = course_ids | all_kp_ids
    for n in NEWS_GRAPH["nodes"]:
        if n.id in all_ids:
            node_map[n.id] = {"id": n.id, "label": n.label, "name": n.name}

    edges_out = []
    for e in NEWS_GRAPH["edges"]:
        if e.source_id in all_ids and e.target_id in all_ids:
            edges_out.append({"source": e.source_id, "target": e.target_id, "relation": e.relation})

    return {"nodes": list(node_map.values()), "edges": edges_out}


def get_skill_pathways(program_name: str) -> list[dict]:
    """从辅修专业出发，查询 课程→知识→技能→职业 映射链。"""
    program_courses = [n for n in NEWS_GRAPH["nodes"]
                       if n.label == "Course"]  # 简化：全量课程

    course_ids = {c.id for c in program_courses}
    # 收集技能
    skill_map: dict[str, dict] = {}
    for e in NEWS_GRAPH["edges"]:
        if e.relation == "MAPS_TO_SKILL" and e.source_id in course_ids:
            skill = next((n for n in NEWS_GRAPH["nodes"] if n.id == e.target_id), None)
            if skill:
                kp = next((n for n in NEWS_GRAPH["nodes"] if n.id == e.source_id), None)
                sid = skill.id
                if sid not in skill_map:
                    skill_map[sid] = {
                        "skill_name": skill.name,
                        "knowledge_points": [],
                        "careers": [],
                    }
                if kp:
                    skill_map[sid]["knowledge_points"].append(kp.name)

    # 技能→职业
    for e in NEWS_GRAPH["edges"]:
        if e.relation == "MATCHES_CAREER":
            if e.source_id in skill_map:
                career = next((n for n in NEWS_GRAPH["nodes"] if n.id == e.target_id), None)
                if career:
                    skill_map[e.source_id]["careers"].append(career.name)

    return list(skill_map.values())


def get_prerequisites(node_id: str) -> list[str]:
    """递归获取某节点的所有先修节点（DFS 闭包）。"""
    result: list[str] = []
    seen: set[str] = set()

    def dfs(current: str):
        if current in seen:
            return
        seen.add(current)
        for e in NEWS_GRAPH["edges"]:
            if e.relation == "REQUIRES" and e.target_id == current:
                result.append(e.source_id)
                dfs(e.source_id)

    dfs(node_id)
    return result
