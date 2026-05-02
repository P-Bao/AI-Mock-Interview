from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass

from .gemini_client import call_gemini_text


def encode_node(title: str, level: str) -> str:
    return f"{title}||{level}"


def decode_node(code: str):
    title, level = code.split("||")
    return title, level


class CareerGraph:
    def __init__(self):
        self.graph = {}

    def add_edge(self, title_u, level_u, title_v, level_v, probability):
        u = encode_node(title_u, level_u)
        v = encode_node(title_v, level_v)
        self.graph.setdefault(u, {})[v] = probability

    def best_path(self, start_code: str, end_code: str):
        pq = [(0.0, start_code, [start_code])]
        visited = {}
        while pq:
            cost, u, path = heapq.heappop(pq)
            if u == end_code:
                return path, math.exp(-cost)
            if u in visited and visited[u] <= cost:
                continue
            visited[u] = cost
            for v, prob in self.graph.get(u, {}).items():
                if prob > 0:
                    heapq.heappush(pq, (cost - math.log(prob), v, path + [v]))
        return None, None


def compute_skill_gap(current_requirements, target_requirements):
    return list(set(target_requirements) - set(current_requirements))


def generate_career_guidance(skill_gap, best_path, api_key: str | None = None) -> str:
    system_prompt = """
You are an experienced career advisor specializing in IT job transitions.
Provide clear, structured, and actionable advice based on the skill gap and the recommended transition path.
"""
    user_prompt = f"""
Skill gap (missing requirements):
{json.dumps(skill_gap, indent=2, ensure_ascii=False)}

Recommended transition path:
{[decode_node(n) for n in best_path] if best_path else []}

Your tasks:
1. Explain why this transition path is reasonable.
2. Explain the missing skills and why they matter.
3. Recommend a structured learning plan and concrete next steps.
4. Give motivational and practical guidance for reaching the target role.
"""
    return call_gemini_text(system_prompt=system_prompt, user_prompt=user_prompt, api_key=api_key)


def career_guidance_pipeline(
    graph: CareerGraph,
    current_title: str,
    current_level: str,
    target_title: str,
    target_level: str,
    current_requirements: list,
    target_requirements: list,
    api_key: str | None = None,
):
    v_c = encode_node(current_title, current_level)
    v_t = encode_node(target_title, target_level)
    best_path, probability_score = graph.best_path(v_c, v_t)
    if best_path is None:
        raise ValueError("No valid transition path found.")

    skill_gap = compute_skill_gap(current_requirements, target_requirements)
    guidance = generate_career_guidance(skill_gap, best_path, api_key=api_key)
    return {
        "best_path": [decode_node(n) for n in best_path],
        "path_probability": probability_score,
        "skill_gap": skill_gap,
        "guidance": guidance,
    }
