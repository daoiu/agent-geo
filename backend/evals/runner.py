"""评测运行入口占位 — 阶段 1 Task 1 完整实现。"""
from __future__ import annotations


async def run_all() -> dict:
    """运行全部评测用例,返回聚合报告占位。"""
    return {
        "total": 0,
        "pass": 0,
        "pass_rate": 0.0,
        "details": [],
        "_note": "阶段 0 占位;阶段 1 Task 1 接入真实 judge",
    }


if __name__ == "__main__":
    import asyncio

    report = asyncio.run(run_all())
    print(report)