"""HTML + PDF report renderer using Jinja2 and WeasyPrint."""
from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.models.schemas import Report

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )


def render_html(report: Report) -> str:
    """Render report to HTML string using Jinja2 template."""
    env = _get_env()
    template = env.get_template("report.html.j2")
    return template.render(report=report)


def render_pdf(report: Report, output_path: str) -> str:
    """Render report to PDF file. Returns the output path."""
    # Deferred import: WeasyPrint requires GTK3 runtime which may not be
    # available on all platforms (e.g., Windows without GTK3 installed).
    from weasyprint import CSS, HTML

    html_str = render_html(report)
    css_path = _TEMPLATE_DIR / "report.css"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    html = HTML(string=html_str, base_url=str(_TEMPLATE_DIR))
    html.write_pdf(output_path, stylesheets=[CSS(filename=str(css_path))])
    return output_path
