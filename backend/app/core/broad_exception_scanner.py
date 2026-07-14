"""宽泛异常扫描器(P2#33 / Task 42)。

扫描 .py 文件中的:
- `except Exception:` — 宽泛捕获,应改为具体异常
- `except:` — 裸 except,应改为具体异常

输出:
- list[Finding] (file_path, line_number, pattern, severity)
- report_by_file(findings): 按文件分组

哲学:
- 入口兜底(如 main.py 顶层)可保留 except Exception
- 业务逻辑层必须用具体异常
- 测试文件可豁免
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Finding:
    __test__ = False  # 防止 pytest 把它当 test class
    file_path: Path
    line_number: int
    pattern: str  # "except Exception" | "except:" | "noqa: BLE001"
    severity: str  # "warn" | "error"
    line_text: str = ""


def _scan_file(path: Path) -> list[Finding]:
    """扫描单个 .py 文件,返回 finding 列表。"""
    findings: list[Finding] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return findings

    # 1) AST 扫描: except Exception / 裸 except
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                # 裸 except:
                findings.append(
                    Finding(
                        file_path=path,
                        line_number=node.lineno,
                        pattern="except:",
                        severity="error",
                    )
                )
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                findings.append(
                    Finding(
                        file_path=path,
                        line_number=node.lineno,
                        pattern="except Exception",
                        severity="error",
                    )
                )

    # 2) noqa: BLE001 检测(行级)
    for i, line in enumerate(source.splitlines(), start=1):
        if "noqa: BLE001" in line or "noqa:BLE001" in line:
            findings.append(
                Finding(
                    file_path=path,
                    line_number=i,
                    pattern="noqa: BLE001",
                    severity="warn",
                    line_text=line.strip(),
                )
            )

    return findings


def scan_broad_exceptions(
    paths: Iterable[Path],
    skip_tests: bool = True,
) -> list[Finding]:
    """扫描多个目录/文件,返回所有 findings。"""
    all_findings: list[Finding] = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            all_findings.extend(_scan_file(p))
        elif p.is_dir():
            for py_file in p.rglob("*.py"):
                if skip_tests and ("test" in py_file.name.lower() or "/tests/" in str(py_file)):
                    continue
                all_findings.extend(_scan_file(py_file))
    return all_findings


def report_by_file(findings: list[Finding]) -> dict[str, list[Finding]]:
    """按文件名分组 findings(返回 {filename: [findings]})。"""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.file_path.name].append(f)
    return dict(grouped)


__all__ = [
    "Finding",
    "scan_broad_exceptions",
    "report_by_file",
]


if __name__ == "__main__":
    """CLI:扫描 app/ 输出报告。"""
    import sys

    targets = [Path(p) for p in sys.argv[1:]] or [Path("app")]
    findings = scan_broad_exceptions(targets)
    grouped = report_by_file(findings)

    total = len(findings)
    print(f"扫描完成: {total} 处宽泛异常捕获")
    print(f"涉及文件数: {len(grouped)}")
    print()
    for fname, file_findings in sorted(grouped.items()):
        print(f"  {fname}: {len(file_findings)} 处")
        for f in file_findings[:3]:
            print(f"    L{f.line_number}: {f.pattern}")

    if total > 0:
        print(f"\n[建议] 改用 _LLM_TRANSIENT_EXCEPTIONS 或具体异常类")
        sys.exit(1 if any(f.severity == "error" for f in findings) else 0)