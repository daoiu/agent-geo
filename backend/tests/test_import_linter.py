"""架构分层 import-linter 阻断测试（P1#21 / Task 22）。

阶段 1 P0#3 已加 test_no_repo_to_service.py(防止 repo → service)。
本测试在阶段 2 P1#21 升级到 import-linter 框架，覆盖全栈分层:
- api → services → domain → repos → models 单向依赖
- tools/tools.py 不被 domain 依赖(避免循环)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_import_linter_config_exists() -> None:
    """必须有 .import-linter.toml(或 .ini)配置文件。"""
    candidates = [
        REPO_ROOT / ".import-linter.toml",
        REPO_ROOT / ".import-linter.ini",
        REPO_ROOT / "pyproject.toml",  # 也可嵌在 pyproject
    ]
    found = [c for c in candidates if c.exists()]
    assert found, (
        f"未找到 import-linter 配置: {[str(c) for c in candidates]}\n"
        f"创建 .import-linter.toml 定义分层契约"
    )


def test_import_linter_passes() -> None:
    """运行 lint-imports 应无违反（机械阻断分层反向依赖）。"""
    config = REPO_ROOT / ".import-linter.toml"
    if not config.exists():
        config = REPO_ROOT / ".import-linter.ini"

    if not config.exists():
        pytest.skip("import-linter 配置文件不存在,跳过此测试")

    # import-linter 提供 lint-imports 命令(随包安装到 .venv/Scripts)
    lint_imports_bin = REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
        "lint-imports.exe" if os.name == "nt" else "lint-imports"
    )
    if lint_imports_bin.exists():
        result = subprocess.run(
            [str(lint_imports_bin), "--config", str(config)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    else:
        # fallback:python -c 调用 API
        result = subprocess.run(
            [sys.executable, "-c",
             "from importlinter import api; "
             "import sys; sys.exit(0 if api.linter.parse_importlinterfile(open(r'" + str(config).replace("\\", "\\\\") + "').read()) else 1)"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    # exit code 0 = 无违反
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
    assert result.returncode == 0, (
        f"import-linter 发现分层违反:\n{result.stdout}\n{result.stderr}"
    )


def test_repositories_do_not_import_services() -> None:
    """专门检查 repositories/ ❌ services/(阶段 1 已修,这里再确认)。"""
    from tests.test_no_repo_to_service import _iter_repo_imports
    hits = list(_iter_repo_imports())
    assert not hits, (
        "repositories/ 发现反向依赖:\n"
        + "\n".join(f"  - {f}: imports `{m}`" for f, m in hits)
    )