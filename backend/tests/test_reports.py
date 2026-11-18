"""Tests for PDF report generation, SVG charts, Jinja2 autoescape, and SSRF protection."""

from __future__ import annotations

import base64
import pytest

from app.reports.charts import (
    generate_dispatch_mix_chart_svg,
    generate_screening_curves_svg,
    generate_storage_chart_svg,
)
from app.reports.pdf_generator import (
    BlockedURLFetchError,
    generate_technical_report_pdf,
    render_report_html,
    safe_url_fetcher,
)


def _weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401
        weasyprint.HTML(string="<p>ok</p>", url_fetcher=safe_url_fetcher).write_pdf()
        return True
    except Exception:
        return False


def test_ssrf_url_fetcher_blocks_external_and_local_urls():
    for bad_url in [
        "http://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/pixel.png",
        "file:///etc/passwd",
        "ftp://internal/secret",
        "data:text/html;base64,PHNjcmlwdD4=",
    ]:
        with pytest.raises(BlockedURLFetchError):
            safe_url_fetcher(bad_url)

    # Valid embedded SVG data URI succeeds
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")
    res = safe_url_fetcher(uri)
    assert res["mime_type"] == "image/svg+xml"
    assert res["string"] == svg


def test_jinja2_autoescape_blocks_html_injection():
    html = render_report_html(
        {
            "project_name": "<script>alert(1)</script>",
            "classroom_name": "Turma <b>A</b>",
            "author_name": "Aluno",
            "author_email": "a@b.com",
            "generated_at": "01/01/2026",
            "hydro_plants": [],
            "thermal_plants": [],
            "config": {
                "start_month": 1,
                "start_year": 2023,
                "end_month": 12,
                "end_year": 2023,
                "load_mwm": 1000.0,
            },
            "summary": {
                "ea_max_mwm": 1000.0,
                "total_cost_kusd_year": 500.0,
                "max_deficit_mwm": 0.0,
                "avg_ena_mwm": 800.0,
                "avg_thermal_mwm": 200.0,
                "deficit_months": 0,
                "critical_period": None,
                "economics": [],
            },
            "monthly_results": [],
            "include_monthly_table": False,
            "storage_svg": "",
            "dispatch_svg": "",
            "screening_svg": "",
        }
    )
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_svg_charts_generation():
    monthly = [
        {
            "year": 2023,
            "month": m,
            "earm_pct": max(10.0, 90.0 - m * 5.0),
            "gh_delivered_mwm": 800.0,
            "deficit_mwm": 0.0,
            "thermal_dispatch_by_plant": {"t1": 200.0},
        }
        for m in range(1, 13)
    ]
    svg1 = generate_storage_chart_svg(
        monthly, {"start_year": 2023, "start_month": 5, "end_year": 2023, "end_month": 12}
    )
    svg2 = generate_dispatch_mix_chart_svg(
        monthly, {"t1": {"name": "Carvao", "fuel_type": "COAL"}}, 1000.0
    )
    svg3 = generate_screening_curves_svg(
        [
            {
                "name": "Carvao",
                "fuel_type": "COAL",
                "points": [
                    {"hours": 0.0, "unit_cost_usd_kw_year": 200.0},
                    {"hours": 8640.0, "unit_cost_usd_kw_year": 550.0},
                ],
            }
        ],
        10.0,
    )
    for uri in (svg1, svg2, svg3):
        assert uri.startswith("data:image/svg+xml;base64,")


@pytest.mark.skipif(
    not _weasyprint_available(),
    reason="WeasyPrint native Cairo/Pango runtime not installed on host (validated inside Docker)",
)
def test_generate_valid_pdf_bytes():
    monthly = [
        {
            "year": 2023,
            "month": m,
            "enat_mwm": 900.0,
            "total_thermal_mwm": 200.0,
            "gh_delivered_mwm": 800.0,
            "earm_mwm": 2000.0,
            "earm_pct": 65.0,
            "evert_mwm": 0.0,
            "deficit_mwm": 0.0,
            "thermal_dispatch_by_plant": {"t1": 200.0},
        }
        for m in range(1, 7)
    ]
    pdf = generate_technical_report_pdf(
        project_name="Projeto Teste PDF",
        classroom_name="Turma 2026",
        author_name="Aluno Teste",
        author_email="aluno@gerat.local",
        generated_at="01/01/2026 12:00 UTC",
        hydro_plants=[
            {
                "id": "h1",
                "name": "Sobradinho",
                "vmax_hm3": 34116.0,
                "vmin_hm3": 5447.0,
                "productivity_mw_m3s": 0.25,
                "installed_power_mw": 1050.0,
            }
        ],
        thermal_plants=[
            {
                "id": "t1",
                "name": "UTE Carvao",
                "fuel_type": "COAL",
                "installed_power_mw": 500.0,
                "fc_max": 0.85,
                "fc_min": 0.1,
                "fixed_cost_usd_kw": 2000.0,
                "variable_cost_usd_mwh": 42.0,
                "useful_life_years": 30,
            }
        ],
        config_snapshot={
            "load_mwm": 1000.0,
            "start_year": 2023,
            "start_month": 1,
            "end_year": 2023,
            "end_month": 6,
            "interest_rate_pct": 10.0,
        },
        summary={
            "ea_max_mwm": 3433.64,
            "total_cost_kusd_year": 125000.0,
            "max_deficit_mwm": 0.0,
            "avg_ena_mwm": 900.0,
            "avg_thermal_mwm": 200.0,
            "deficit_months": 0,
            "critical_period": {
                "start_year": 2023,
                "start_month": 1,
                "end_year": 2023,
                "end_month": 6,
                "duration_months": 6,
            },
            "economics": [
                {
                    "name": "UTE Carvao",
                    "avg_generation_mwm": 200.0,
                    "frc": 0.1061,
                    "fixed_cost_kusd_year": 106079.0,
                    "variable_cost_kusd_year": 72576.0,
                    "total_cost_kusd_year": 178655.0,
                }
            ],
        },
        monthly_results=monthly,
        screening_series=[
            {
                "name": "UTE Carvao",
                "fuel_type": "COAL",
                "points": [
                    {"hours": 0.0, "unit_cost_usd_kw_year": 212.0},
                    {"hours": 8640.0, "unit_cost_usd_kw_year": 575.0},
                ],
            }
        ],
        include_monthly_table=True,
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5000
