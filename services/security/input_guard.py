"""提示注入检测——ponytail: 关键词匹配，生产换 LLM-based 检测或 guardrails 库。"""

import re

INJECTION_PATTERNS = [
    # 系统提示泄露
    r"(忽略|忘记|无视).{0,10}(以上|之前|前面).{0,10}(指令|指示|说明|要求|规则)",
    r"(你.{0,5}是|你现在是|你扮演|你假装).{0,15}(角色|身份)",
    r"(system\s*prompt|系统提示|系统指令)",
    r"(reveal|disclose|output|print|show|tell\s+me).{0,20}(your\s+)?(prompt|instruction|system)",
    # 越狱
    r"DAN\s*(mode|模式)",
    r"(jailbreak|越狱)",
    r"(ignore|forget).{0,10}(previous|above).{0,10}(instruction|direction|rule)",
    # 目标劫持
    r"(从现在开始|从今以后|从现在起).{0,20}(你的.{0,5}(任务|目标|职责)是)",
    # 数据泄露
    r"(输出|打印|显示|告诉我).{0,10}(所有|全部).{0,5}(用户|对话|消息|历史)",
]


def detect_injection(message: str) -> list[str]:
    """返回匹配到的注入模式，空列表表示通过检测。"""
    hits = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            hits.append(pattern)
    return hits
