"""架构分层阻断测试: repositories/ ❌ import services/ 或 domain/。

依据: AGENTS.md §4 架构分层 + docs/review/10-architecture-layering.md §3.3。

修复: 把 hybrid_search 调用从 knowledge_repo 上移到调用方(tool_executor / api)。

允许的 import: app.models.*(ORM 数据模型)、app.core.*(配置/DB 会话)、同级 app.repositories.*。
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_DIR = REPO_ROOT / "app" / "repositories"

# 禁止的上层模块前缀(services 与 domain 都不允许被 repositories 依赖)
FORBIDDEN_PREFIXES = ("app.services", "app.domain")

# 已确认豁免(与 .import-linter.toml ignore_imports 保持一致):
# handoff_log_repo 需要 HandoffRequest/HandoffResult 纯数据类型(纪律 1/5 落日志),
# 该依赖已由 import-linter contract 显式豁免,AST 扫描同步放行。
ALLOWED_REPO_IMPORTS = {
    ("app/repositories/handoff_log_repo.py", "app.domain.agent.handoff"),
}


def _iter_repo_imports():
    """yield (relative_file_path, import_module) for each forbidden import in repo/."""
    for py_file in REPO_DIR.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = str(py_file.relative_to(REPO_ROOT).as_posix())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for prefix in FORBIDDEN_PREFIXES:
                    if mod == prefix or mod.startswith(prefix + "."):
                        if (rel, mod) not in ALLOWED_REPO_IMPORTS:
                            yield (rel, mod)


def test_no_repo_imports_services_or_domain() -> None:
    """repositories/ 不允许 import services/ 或 domain/。

    发现违反时,需把 services/domain 调用上移到调用方(tool_executor / api / service 层)。
    """
    hits = list(_iter_repo_imports())
    assert not hits, (
        "repositories/ 发现反向依赖(违反 AGENTS.md §4):\n"
        + "\n".join(f"  - {f}: imports `{m}`" for f, m in hits)
        + "\n\n修复方向: 把 services/domain 调用上移到 tool_executor/api 层。"
    )