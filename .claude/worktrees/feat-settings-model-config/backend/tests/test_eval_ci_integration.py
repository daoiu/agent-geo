"""P1#27（Task 28）: 评测集与 CI 集成验证。

目标:
- CI 必须包含 evals 步骤
- evals 步骤用 OPENAI_API_KEY secret(无 secret 时不崩)
- evals 步骤失败不阻塞 CI(continue-on-error 或 || echo)
- runner 可作为 `python -m evals.runner` 调用,缺 OPENAI_API_KEY 时不抛
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
EVALS_RUNNER_PATH = REPO_ROOT / "backend" / "evals" / "runner.py"


@pytest.fixture(scope="module")
def ci_config() -> dict:
    """Read .github/workflows/ci.yml once per module."""
    assert CI_PATH.exists(), f"CI workflow missing at {CI_PATH}"
    return yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))


def _find_eval_step(ci_config: dict) -> tuple[str, dict] | None:
    """找到真正的 evals runner 步骤(必须有 OPENAI_API_KEY env)。

    避免把 'ruff check ... evals/' 误识别为 evals runner 步骤。
    """
    for job_name, job in ci_config.get("jobs", {}).items():
        for step in job.get("steps", []):
            env = step.get("env") or {}
            if "OPENAI_API_KEY" in env:
                return job_name, step
    return None


def test_ci_workflow_includes_evals_step(ci_config: dict) -> None:
    """CI workflow 至少一个 job 包含跑 evals.runner 的步骤(env 含 OPENAI_API_KEY)。"""
    found = _find_eval_step(ci_config)
    assert found is not None, "CI 必须包含跑 evals.runner 的步骤(env 含 OPENAI_API_KEY)"


def test_ci_evals_step_uses_openai_api_key_from_secrets(ci_config: dict) -> None:
    """evals 步骤必须用 `${{ secrets.OPENAI_API_KEY }}`(非硬编码)。"""
    found = _find_eval_step(ci_config)
    assert found is not None, "CI 必须包含 evals runner 步骤"
    job_name, step = found
    env = step.get("env") or {}
    api_key_ref = env.get("OPENAI_API_KEY", "")
    assert api_key_ref == "${{ secrets.OPENAI_API_KEY }}", (
        f"evals step in job '{job_name}' must reference "
        f"${{ secrets.OPENAI_API_KEY }} from secrets; got {api_key_ref!r}"
    )
    # 不能有 sk- 开头的硬编码 key(简单 grep)
    run = step.get("run") or ""
    assert "sk-" not in run, "硬编码 API key 不允许"


def test_ci_evals_step_tolerates_failure(ci_config: dict) -> None:
    """evals 步骤必须允许失败(`|| true` / `|| echo` / `continue-on-error`)。"""
    found = _find_eval_step(ci_config)
    assert found is not None, "CI 必须包含 evals runner 步骤"
    job_name, step = found
    run = (step.get("run") or "").lower()
    has_continue_on_error = step.get("continue-on-error") is True
    has_shell_fallback = "|| true" in run or "|| echo" in run
    assert has_continue_on_error or has_shell_fallback, (
        f"evals step in job '{job_name}' must tolerate failure "
        "(use 'continue-on-error: true' or '|| true' / '|| echo' in run)"
    )


def test_ci_evals_step_runs_evaluations(ci_config: dict) -> None:
    """evals 步骤必须实际调用 evals.runner 或 evals 相关命令。"""
    found = _find_eval_step(ci_config)
    assert found is not None, "CI 必须包含 evals runner 步骤"
    _, step = found
    run = (step.get("run") or "").lower()
    # 必须实际调用 evals 模块
    assert "evals" in run and ("python" in run or "pytest" in run), (
        f"evals step must invoke python evals module; got run={run!r}"
    )


def test_evals_runner_runnable_without_openai_api_key() -> None:
    """`python -m evals.runner` 在缺 OPENAI_API_KEY 时不应抛(允许 stderr 输出)。"""
    # 移除 env var 模拟 CI 缺 secret 场景
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_BASE_URL", None)

    result = subprocess.run(
        [sys.executable, "-m", "evals.runner"],
        cwd=REPO_ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # runner 返回 0 或带 JSON 输出即视为 OK
    stdout = result.stdout or ""
    assert "pass_rate" in stdout, (
        f"runner output must include 'pass_rate'; got stdout={stdout[:500]}"
    )


def test_evals_runner_emits_machine_readable_report() -> None:
    """runner 必须输出 machine-readable JSON 报告(含 total/pass/pass_rate/avg_score)。"""
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_BASE_URL", None)

    result = subprocess.run(
        [sys.executable, "-m", "evals.runner"],
        cwd=REPO_ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    stdout = result.stdout or ""
    # 必须包含全部 4 个关键字段
    for field in ["total", "pass_rate", "avg_score", "avg_latency_ms"]:
        assert field in stdout, f"runner output must contain '{field}'"


def test_evals_runner_file_exists() -> None:
    """evals/runner.py 必须存在(防文件被误删导致 CI 静默通过)。"""
    assert EVALS_RUNNER_PATH.exists(), f"missing {EVALS_RUNNER_PATH}"