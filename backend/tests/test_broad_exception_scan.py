"""P2#33（Task 42）: 移除 noqa: BLE001 宽泛捕获测试。

目标:
- 提供扫描脚本,找出所有 except Exception / except: 模式
- 收敛到 _LLM_TRANSIENT_EXCEPTIONS 或具体异常
- 报告扫描结果(剩余宽泛捕获数)
- 测试扫描脚本自身
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_broad_exception_scanner_finds_handlers() -> None:
    """扫描器必须能找到 except Exception / except: 模式。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    # 构造临时目录测试
    test_dir = Path(__file__).parent / "_test_scan_input"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "good.py").write_text(
            "try:\n"
            "    pass\n"
            "except ValueError:\n"
            "    pass\n",
            encoding="utf-8",
        )
        (test_dir / "bad.py").write_text(
            "try:\n"
            "    pass\n"
            "except Exception:\n"
            "    pass\n",
            encoding="utf-8",
        )
        (test_dir / "bad2.py").write_text(
            "try:\n"
            "    pass\n"
            "except:\n"
            "    pass\n",
            encoding="utf-8",
        )

        findings = scan_broad_exceptions([test_dir])
        files = {f.file_path.name for f in findings}
        assert "bad.py" in files
        assert "bad2.py" in files
        assert "good.py" not in files
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()


def test_broad_exception_scanner_reports_line_number() -> None:
    """扫描器必须报告行号。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    test_dir = Path(__file__).parent / "_test_scan_input2"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "sample.py").write_text(
            "def f():\n"           # line 1
            "    try:\n"           # line 2
            "        x = 1\n"      # line 3
            "    except Exception:\n"  # line 4
            "        pass\n",      # line 5
            encoding="utf-8",
        )
        findings = scan_broad_exceptions([test_dir])
        assert len(findings) == 1
        assert findings[0].line_number == 4
        assert findings[0].pattern == "except Exception"
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()


def test_broad_exception_scanner_skips_tests_dir() -> None:
    """扫描器默认跳过 tests/ 目录(测试文件允许宽泛捕获)。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    # 创建模拟 tests 目录
    test_dir = Path(__file__).parent / "_fake_tests"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "test_x.py").write_text(
            "try:\n    pass\nexcept Exception:\n    pass\n",
            encoding="utf-8",
        )
        findings = scan_broad_exceptions([test_dir], skip_tests=True)
        assert len(findings) == 0
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()


def test_broad_exception_scanner_handles_empty_dir() -> None:
    """空目录不应抛。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    test_dir = Path(__file__).parent / "_empty_dir"
    test_dir.mkdir(exist_ok=True)
    try:
        findings = scan_broad_exceptions([test_dir])
        assert findings == []
    finally:
        test_dir.rmdir()


def test_scanner_finds_bare_except() -> None:
    """扫描器必须找到裸 except: 模式。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    test_dir = Path(__file__).parent / "_test_bare_except"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "x.py").write_text(
            "try:\n    x = 1\nexcept:\n    pass\n",
            encoding="utf-8",
        )
        findings = scan_broad_exceptions([test_dir])
        assert any(f.pattern == "except:" for f in findings)
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()


def test_scanner_handles_syntax_error_gracefully() -> None:
    """语法错误的文件不应让扫描器崩溃。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    test_dir = Path(__file__).parent / "_test_syntax_err"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "broken.py").write_text(
            "def incomplete(:\n",
            encoding="utf-8",
        )
        findings = scan_broad_exceptions([test_dir])
        # 不抛即通过
        assert isinstance(findings, list)
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()


def test_finding_has_severity() -> None:
    """每个 finding 必须有 severity(warn/error)。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions

    test_dir = Path(__file__).parent / "_test_severity"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "x.py").write_text(
            "try:\n    pass\nexcept Exception:\n    pass\n",
            encoding="utf-8",
        )
        findings = scan_broad_exceptions([test_dir])
        assert len(findings) >= 1
        assert findings[0].severity in ("warn", "error")
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()


def test_report_groups_by_file() -> None:
    """报告应按文件分组。"""
    from app.core.broad_exception_scanner import scan_broad_exceptions, report_by_file

    test_dir = Path(__file__).parent / "_test_group"
    test_dir.mkdir(exist_ok=True)
    try:
        (test_dir / "a.py").write_text(
            "try:\n    pass\nexcept Exception:\n    pass\n"
            "try:\n    pass\nexcept Exception:\n    pass\n",
            encoding="utf-8",
        )
        (test_dir / "b.py").write_text(
            "try:\n    pass\nexcept:\n    pass\n",
            encoding="utf-8",
        )
        findings = scan_broad_exceptions([test_dir])
        grouped = report_by_file(findings)
        assert "a.py" in grouped
        assert "b.py" in grouped
        assert len(grouped["a.py"]) == 2  # a.py 有 2 处
        assert len(grouped["b.py"]) == 1
    finally:
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()