"""Vector SVG chart generation using Matplotlib OO API (Figure + Agg, never pyplot)."""

from __future__ import annotations

import base64
import io
from collections.abc import Sequence
from typing import Any

import matplotlib

matplotlib.use("Agg")

from matplotlib.backends.backend_svg import FigureCanvasSVG  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

# Synchronized palette (Web & PDF)
PALETTE = {
    "HYDRO": "#0284c7",
    "COAL": "#d97706",
    "OIL": "#ea580c",
    "NUCLEAR": "#4f46e5",
    "GAS": "#059669",
    "OTHER": "#64748b",
    "DEFICIT": "#dc2626",
    "LOAD": "#0f172a",
    "CRITICAL_BG": "#fee2e2",
}


def _figure_to_svg_data_uri(fig: Figure) -> str:
    """Render a Matplotlib Figure to a base64-encoded SVG data URI."""
    buf = io.BytesIO()
    canvas = FigureCanvasSVG(fig)
    canvas.print_svg(buf)
    svg_bytes = buf.getvalue()
    b64 = base64.b64encode(svg_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def generate_storage_chart_svg(
    monthly_results: Sequence[dict[str, Any]],
    critical_period: dict[str, Any] | None,
) -> str:
    """SVG chart of Reservoir Storage (%EA) with Critical Period shaded."""
    fig = Figure(figsize=(8.2, 3.0), dpi=120)
    ax = fig.add_subplot(111)

    if not monthly_results:
        ax.text(0.5, 0.5, "Sem dados mensais", ha="center", va="center")
        return _figure_to_svg_data_uri(fig)

    labels = [f"{r['year']}-{r['month']:02d}" for r in monthly_results]
    x = list(range(len(labels)))
    earm_pct = [float(r.get("earm_pct", 0.0)) for r in monthly_results]

    ax.plot(x, earm_pct, color=PALETTE["HYDRO"], linewidth=1.8, label="Armazenamento (% EAmax)")
    ax.fill_between(x, earm_pct, 0, color=PALETTE["HYDRO"], alpha=0.15)

    # Shade critical period
    if critical_period:
        cp_start = (critical_period["start_year"], critical_period["start_month"])
        cp_end = (critical_period["end_year"], critical_period["end_month"])
        idxs = [
            i
            for i, r in enumerate(monthly_results)
            if cp_start <= (r["year"], r["month"]) <= cp_end
        ]
        if idxs:
            ax.axvspan(
                idxs[0],
                idxs[-1],
                color=PALETTE["DEFICIT"],
                alpha=0.14,
                label="Período Crítico",
            )

    step = max(1, len(labels) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], fontsize=7, rotation=25, ha="right")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Armazenamento (%)", fontsize=8)
    ax.set_title("Evolução do Armazenamento no REE e Período Crítico", fontsize=10, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", fontsize=7.5, frameon=True)
    fig.tight_layout()

    return _figure_to_svg_data_uri(fig)


def generate_dispatch_mix_chart_svg(
    monthly_results: Sequence[dict[str, Any]],
    thermal_meta: dict[str, dict[str, str]],
    load_mwm: float,
) -> str:
    """SVG stacked area chart of Generation Mix (Hydro + Thermals by fuel + Deficit) vs Load."""
    fig = Figure(figsize=(8.2, 3.2), dpi=120)
    ax = fig.add_subplot(111)

    if not monthly_results:
        ax.text(0.5, 0.5, "Sem dados mensais", ha="center", va="center")
        return _figure_to_svg_data_uri(fig)

    labels = [f"{r['year']}-{r['month']:02d}" for r in monthly_results]
    x = list(range(len(labels)))

    hydro = [float(r.get("gh_delivered_mwm", 0.0)) for r in monthly_results]
    deficit = [float(r.get("deficit_mwm", 0.0)) for r in monthly_results]

    fuel_order = ["NUCLEAR", "COAL", "GAS", "OIL", "OTHER"]
    fuel_labels = {
        "NUCLEAR": "Nuclear",
        "COAL": "Carvão",
        "GAS": "Gás Natural",
        "OIL": "Óleo",
        "OTHER": "Outras Térmicas",
    }
    fuel_series: dict[str, list[float]] = {f: [0.0] * len(monthly_results) for f in fuel_order}

    for i, r in enumerate(monthly_results):
        disp = r.get("thermal_dispatch_by_plant") or {}
        for pid, val in disp.items():
            ftype = thermal_meta.get(pid, {}).get("fuel_type", "OTHER")
            if ftype not in fuel_series:
                ftype = "OTHER"
            fuel_series[ftype][i] += float(val)

    stack_vals: list[list[float]] = [hydro]
    stack_labels: list[str] = ["Hidráulica"]
    stack_colors: list[str] = [PALETTE["HYDRO"]]

    for f in fuel_order:
        if any(v > 0.0 for v in fuel_series[f]):
            stack_vals.append(fuel_series[f])
            stack_labels.append(fuel_labels[f])
            stack_colors.append(PALETTE[f])

    if any(v > 0.0 for v in deficit):
        stack_vals.append(deficit)
        stack_labels.append("Déficit")
        stack_colors.append(PALETTE["DEFICIT"])

    ax.stackplot(x, *stack_vals, labels=stack_labels, colors=stack_colors, alpha=0.88)
    ax.axhline(
        load_mwm,
        color=PALETTE["LOAD"],
        linestyle="--",
        linewidth=1.4,
        label=f"Carga ({load_mwm:,.0f} MWmês)",
    )

    step = max(1, len(labels) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], fontsize=7, rotation=25, ha="right")
    ax.set_ylabel("Potência Média (MWmês)", fontsize=8)
    ax.set_title("Composição da Geração Hidrotérmica e Atendimento à Carga", fontsize=10, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", fontsize=7, ncol=3, frameon=True)
    fig.tight_layout()

    return _figure_to_svg_data_uri(fig)


def generate_screening_curves_svg(
    screening_series: Sequence[dict[str, Any]],
    interest_rate_pct: float,
) -> str:
    """SVG Screening Curves chart (Unit Cost US$/kW·ano vs Operating Hours [0..8640])."""
    fig = Figure(figsize=(8.2, 3.0), dpi=120)
    ax = fig.add_subplot(111)

    if not screening_series:
        ax.text(0.5, 0.5, "Nenhuma térmica habilitada para curvas de sensibilidade", ha="center", va="center")
        return _figure_to_svg_data_uri(fig)

    for s in screening_series:
        hrs = [p["hours"] for p in s["points"]]
        costs = [p["unit_cost_usd_kw_year"] for p in s["points"]]
        color = PALETTE.get(s.get("fuel_type", "OTHER"), PALETTE["OTHER"])
        ax.plot(hrs, costs, linewidth=2.0, color=color, label=s["name"])

    ax.set_xlim(0, 8640)
    ax.set_xlabel("Horas de Operação Anual (h/ano)", fontsize=8)
    ax.set_ylabel("Custo Total Unitário (US$/kW·ano)", fontsize=8)
    ax.set_title(
        f"Curvas de Sensibilidade (Screening Curves) — Taxa de Juros {interest_rate_pct:.1f}% a.a.",
        fontsize=10,
        fontweight="bold",
    )
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper left", fontsize=7.5, frameon=True)
    fig.tight_layout()

    return _figure_to_svg_data_uri(fig)
