"""Secure PDF technical report generator using WeasyPrint + Jinja2 (SSRF-safe)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.charts import (
    generate_dispatch_mix_chart_svg,
    generate_screening_curves_svg,
    generate_storage_chart_svg,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class BlockedURLFetchError(ValueError):
    """Raised when WeasyPrint attempts to fetch a disallowed URL (SSRF protection)."""


def safe_url_fetcher(url: str, timeout: int = 10, ssl_context: Any = None) -> dict[str, Any]:
    """Custom WeasyPrint url_fetcher that blocks ALL external and local requests.

    Strictly allows only in-memory base64 SVG data URIs (`data:image/svg+xml;base64,...`).
    """
    prefix = "data:image/svg+xml;base64,"
    if not url.startswith(prefix):
        raise BlockedURLFetchError(
            f"Requisição bloqueada por segurança (SSRF): '{url}'. "
            "Apenas assets SVG embutidos em memória (data:image/svg+xml;base64,...) são permitidos."
        )

    raw_b64 = url[len(prefix) :]
    svg_bytes = base64.b64decode(raw_b64)
    return {
        "string": svg_bytes,
        "mime_type": "image/svg+xml",
    }


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"], default_for_string=True, default=True),
    )


def render_report_html(context: dict[str, Any]) -> str:
    env = _get_jinja_env()
    template = env.get_template("report.html")
    return template.render(**context)


def generate_technical_report_pdf(
    *,
    project_name: str,
    classroom_name: str | None,
    author_name: str,
    author_email: str,
    generated_at: str,
    hydro_plants: list[dict[str, Any]],
    thermal_plants: list[dict[str, Any]],
    config_snapshot: dict[str, Any],
    summary: dict[str, Any],
    monthly_results: list[dict[str, Any]],
    screening_series: list[dict[str, Any]],
    include_monthly_table: bool = False,
) -> bytes:
    """Render full technical report HTML + vector SVGs and compile to PDF bytes."""
    import weasyprint  # Imported locally so module imports cleanly even without GTK on dev hosts

    thermal_meta = {
        t["id"]: {"name": t["name"], "fuel_type": t["fuel_type"]}
        for t in thermal_plants
    }

    storage_svg = generate_storage_chart_svg(
        monthly_results, summary.get("critical_period")
    )
    dispatch_svg = generate_dispatch_mix_chart_svg(
        monthly_results,
        thermal_meta,
        float(config_snapshot.get("load_mwm", 0.0)),
    )
    screening_svg = generate_screening_curves_svg(
        screening_series,
        float(config_snapshot.get("interest_rate_pct", 10.0)),
    )

    html_str = render_report_html(
        {
            "project_name": project_name,
            "classroom_name": classroom_name or "Espaço Individual",
            "author_name": author_name,
            "author_email": author_email,
            "generated_at": generated_at,
            "hydro_plants": hydro_plants,
            "thermal_plants": thermal_plants,
            "config": config_snapshot,
            "summary": summary,
            "monthly_results": monthly_results if include_monthly_table else [],
            "include_monthly_table": include_monthly_table,
            "storage_svg": storage_svg,
            "dispatch_svg": dispatch_svg,
            "screening_svg": screening_svg,
        }
    )

    doc = weasyprint.HTML(string=html_str, url_fetcher=safe_url_fetcher)
    pdf_bytes: bytes = doc.write_pdf()
    return pdf_bytes
