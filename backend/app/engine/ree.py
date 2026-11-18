"""Equivalent Energy Reservoir (REE) and Natural Inflow Energy (ENA) calculations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.engine.types import HydroPlantInput, InflowRecordInput, REEResult

# Commercial month of 30 days: 30 * 24 * 3600 * 1e-6 = 2.592 hm3 / (m3/s * month)
SECONDS_PER_COMMERCIAL_MONTH_MILLIONS: float = 2.592


class CascadeCycleError(ValueError):
    """Raised when the hydro plant downstream graph contains a cycle."""


class CascadeReferenceError(ValueError):
    """Raised when a plant references an unknown downstream_plant_id."""


def build_cascades(plants: Sequence[HydroPlantInput]) -> dict[str, list[str]]:
    """Build downstream cascade list for every hydro plant and validate DAG acyclicity.

    For each plant i, Cascata(i) contains plant i followed by all downstream plants
    until downstream_plant_id is None.
    """
    plant_map = {p.plant_id: p for p in plants}
    cascades: dict[str, list[str]] = {}

    for plant in plants:
        visited: set[str] = set()
        chain: list[str] = []
        curr_id: str | None = plant.plant_id

        while curr_id is not None:
            if curr_id in visited:
                raise CascadeCycleError(
                    f"Ciclo detectado na cascata hidrelétrica envolvendo a usina '{curr_id}'."
                )
            if curr_id not in plant_map:
                raise CascadeReferenceError(
                    f"Usina a jusante '{curr_id}' não encontrada para '{plant.plant_id}'."
                )
            visited.add(curr_id)
            chain.append(curr_id)
            curr_id = plant_map[curr_id].downstream_plant_id

        cascades[plant.plant_id] = chain

    return cascades


def calculate_ree(plants: Sequence[HydroPlantInput]) -> REEResult:
    """Compute Equivalent Energy Reservoir (EA_max) for each plant and total system.

    EA_max,i = ((V_max,i - V_min,i) * sum_{k in Cascata(i)} rho_k) / 2.592  [MWmês]
    """
    if not plants:
        return REEResult(
            ea_max_total_mwm=0.0,
            ea_max_by_plant_mwm={},
            cascades={},
            accumulated_productivity={},
        )

    plant_map = {p.plant_id: p for p in plants}
    cascades = build_cascades(plants)

    ea_max_by_plant: dict[str, float] = {}
    accumulated_productivity: dict[str, float] = {}

    for plant in plants:
        if plant.vmax_hm3 < plant.vmin_hm3:
            raise ValueError(
                f"Volume máximo ({plant.vmax_hm3}) menor que volume mínimo ({plant.vmin_hm3}) "
                f"na usina '{plant.name}'."
            )
        if plant.productivity_mw_m3s < 0:
            raise ValueError(
                f"Produtividade negativa ({plant.productivity_mw_m3s}) na usina '{plant.name}'."
            )

        rho_acc = sum(plant_map[k].productivity_mw_m3s for k in cascades[plant.plant_id])
        useful_vol = plant.vmax_hm3 - plant.vmin_hm3
        ea_max_i = (useful_vol * rho_acc) / SECONDS_PER_COMMERCIAL_MONTH_MILLIONS

        accumulated_productivity[plant.plant_id] = rho_acc
        ea_max_by_plant[plant.plant_id] = ea_max_i

    ea_max_total = sum(ea_max_by_plant.values())

    return REEResult(
        ea_max_total_mwm=ea_max_total,
        ea_max_by_plant_mwm=ea_max_by_plant,
        cascades=cascades,
        accumulated_productivity=accumulated_productivity,
    )


def calculate_ena_series(
    plants: Sequence[HydroPlantInput],
    inflows: Sequence[InflowRecordInput],
    ree: REEResult | None = None,
) -> dict[tuple[int, int], float]:
    """Compute monthly Natural Inflow Energy (ENA_t) in MWmês without double counting.

    - If is_incremental == False (total natural inflow Q_nat):
        ENA_t += Q_nat,i,t * rho_i   (individual plant productivity)
    - If is_incremental == True (incremental inflow Q_inc):
        ENA_t += Q_inc,i,t * sum_{k in Cascata(i)} rho_k  (accumulated cascade productivity)
    """
    if ree is None:
        ree = calculate_ree(plants)

    plant_map = {p.plant_id: p for p in plants}
    ena_by_month: dict[tuple[int, int], float] = defaultdict(float)

    for rec in inflows:
        if rec.plant_id not in plant_map:
            continue
        plant = plant_map[rec.plant_id]
        if rec.is_incremental:
            prod = ree.accumulated_productivity[rec.plant_id]
        else:
            prod = plant.productivity_mw_m3s

        ena_by_month[(rec.year, rec.month)] += rec.flow_m3s * prod

    return dict(ena_by_month)
