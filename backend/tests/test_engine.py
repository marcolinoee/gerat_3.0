"""Deterministic unit tests for the GERAT pure Python mathematical engine."""

from __future__ import annotations

import math
import pytest

from app.engine import (
    HOURS_PER_COMMERCIAL_YEAR,
    CascadeCycleError,
    CascadeReferenceError,
    HydroPlantInput,
    InflowRecordInput,
    SimulationConfigInput,
    ThermalPlantInput,
    calculate_ena_series,
    calculate_firm_energy,
    calculate_frc,
    calculate_fuel_cost_from_heat_rate,
    calculate_ree,
    calculate_screening_curves,
    calculate_thermal_economics,
    run_simulation,
)
from app.engine.parsers import (
    MAX_INFLOW_FILE_SIZE_BYTES,
    parse_inflow_file,
    sanitize_csv_cell,
)


class TestREEAndCascade:
    def test_ree_cascade_exact_value(self):
        """Usina2 (Vmax=5000, Vmin=0, rho=0.8) -> Usina3 (rho=0.98) = 3433.641975 MWmês."""
        usina3 = HydroPlantInput(
            plant_id="u3",
            name="Usina3",
            vmax_hm3=0.0,
            vmin_hm3=0.0,
            productivity_mw_m3s=0.98,
            downstream_plant_id=None,
        )
        usina2 = HydroPlantInput(
            plant_id="u2",
            name="Usina2",
            vmax_hm3=5000.0,
            vmin_hm3=0.0,
            productivity_mw_m3s=0.8,
            downstream_plant_id="u3",
        )

        ree = calculate_ree([usina2, usina3])

        assert ree.cascades["u2"] == ["u2", "u3"]
        assert ree.cascades["u3"] == ["u3"]
        assert math.isclose(ree.accumulated_productivity["u2"], 1.78, rel_tol=1e-9)
        assert math.isclose(ree.ea_max_by_plant_mwm["u2"], 3433.641975, abs_tol=1e-6)
        assert math.isclose(ree.ea_max_total_mwm, 3433.641975, abs_tol=1e-6)

    def test_ree_detects_cycle(self):
        u1 = HydroPlantInput("u1", "U1", 1000.0, 0.0, 0.5, downstream_plant_id="u2")
        u2 = HydroPlantInput("u2", "U2", 1000.0, 0.0, 0.5, downstream_plant_id="u1")

        with pytest.raises(CascadeCycleError):
            calculate_ree([u1, u2])

    def test_ree_detects_invalid_downstream_reference(self):
        u1 = HydroPlantInput("u1", "U1", 1000.0, 0.0, 0.5, downstream_plant_id="ghost")

        with pytest.raises(CascadeReferenceError):
            calculate_ree([u1])


class TestENANoDoubleCounting:
    def test_ena_natural_vs_incremental(self):
        """Natural inflow uses individual rho_i; incremental uses accumulated cascade rho."""
        u3 = HydroPlantInput("u3", "U3", 1000.0, 0.0, 0.98, downstream_plant_id=None)
        u2 = HydroPlantInput("u2", "U2", 5000.0, 0.0, 0.80, downstream_plant_id="u3")
        plants = [u2, u3]

        # Natural total flow: Q_nat(u2) = 1000, Q_nat(u3) = 1200 (includes 1000 from u2 + 200 inc)
        # Expected ENA = 1000 * 0.80 + 1200 * 0.98 = 800 + 1176 = 1976.0 MWmês
        inflows_natural = [
            InflowRecordInput("u2", 2020, 1, 1000.0, is_incremental=False),
            InflowRecordInput("u3", 2020, 1, 1200.0, is_incremental=False),
        ]
        ena_nat = calculate_ena_series(plants, inflows_natural)
        assert math.isclose(ena_nat[(2020, 1)], 1976.0, rel_tol=1e-9)

        # Equivalent incremental flows: Q_inc(u2) = 1000, Q_inc(u3) = 200
        # Expected ENA = 1000 * (0.80 + 0.98) + 200 * 0.98 = 1780 + 196 = 1976.0 MWmês
        inflows_incremental = [
            InflowRecordInput("u2", 2020, 1, 1000.0, is_incremental=True),
            InflowRecordInput("u3", 2020, 1, 200.0, is_incremental=True),
        ]
        ena_inc = calculate_ena_series(plants, inflows_incremental)
        assert math.isclose(ena_inc[(2020, 1)], 1976.0, rel_tol=1e-9)


class TestSimulationAndGuideCurve:
    def test_thermal_dispatch_guide_curve_and_gh_max_cap(self):
        """P=2250 MW, FC_max=0.85 => 1912.5 MWmês when %EA < CG; respects gh_max_mwm."""
        hydro = HydroPlantInput("h1", "H1", 2592.0, 0.0, 1.0, downstream_plant_id=None)
        # EA_max = 2592 * 1.0 / 2.592 = 1000.0 MWmês
        thermal = ThermalPlantInput(
            plant_id="t1",
            name="Carvao1",
            fuel_type="COAL",
            installed_power_mw=2250.0,
            fc_max=0.85,
            fc_min=0.10,
            fixed_cost_usd_kw=1500.0,
            variable_cost_usd_mwh=40.0,
            useful_life_years=25,
            guide_curve=[60.0] * 12,
            enabled=True,
        )
        inflows = [
            InflowRecordInput("h1", 2020, 1, 5000.0, is_incremental=False),
            InflowRecordInput("h1", 2020, 2, 5000.0, is_incremental=False),
        ]
        # Start at 50% < 60% -> Month 1 dispatches at FC_max = 1912.5 MWmês
        # Load = 5000 MWmês -> GH_req = 5000 - 1912.5 = 3087.5 MWmês
        # With gh_max_mwm = 2500.0 -> GH_efet = 2500.0, D_pot = 587.5 MWmês
        # EA_tent = 500 + 5000 - 2500 = 3000 -> capped at EA_max=1000, EV=2000
        # Month 2 starts at 100% >= 60% -> dispatches at FC_min = 225.0 MWmês
        cfg = SimulationConfigInput(
            load_mwm=5000.0,
            initial_earm_pct=50.0,
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=2,
            interest_rate_pct=10.0,
            gh_max_mwm=2500.0,
        )

        res = run_simulation([hydro], inflows, [thermal], cfg)
        m1, m2 = res.monthly_results

        assert math.isclose(m1.thermal_dispatch_by_plant["t1"], 1912.5, rel_tol=1e-9)
        assert math.isclose(m1.gh_req_mwm, 3087.5, rel_tol=1e-9)
        assert math.isclose(m1.gh_efet_mwm, 2500.0, rel_tol=1e-9)
        assert math.isclose(m1.deficit_pot_mwm, 587.5, rel_tol=1e-9)
        assert math.isclose(m1.deficit_en_mwm, 0.0, abs_tol=1e-9)
        assert math.isclose(m1.deficit_mwm, 587.5, rel_tol=1e-9)
        assert math.isclose(m1.earm_mwm, 1000.0, rel_tol=1e-9)
        assert math.isclose(m1.evert_mwm, 2000.0, rel_tol=1e-9)

        assert math.isclose(m2.thermal_dispatch_by_plant["t1"], 225.0, rel_tol=1e-9)

    def test_firm_energy_convergence_zero_deficit(self):
        """Firm energy bisection converges within 0.01 MWmês with zero deficit."""
        hydro = HydroPlantInput("h1", "H1", 2592.0, 0.0, 1.0)  # EA_max = 1000 MWmês
        # 6 months: wet then dry
        flows = [1200.0, 1200.0, 400.0, 400.0, 400.0, 1500.0]
        inflows = [
            InflowRecordInput("h1", 2020, m, q, is_incremental=False)
            for m, q in enumerate(flows, start=1)
        ]
        cfg = SimulationConfigInput(
            load_mwm=1000.0,
            initial_earm_pct=100.0,
            start_year=2020,
            start_month=1,
            end_year=2020,
            end_month=6,
        )

        firm = calculate_firm_energy([hydro], inflows, [], cfg, precision_mwm=0.01)

        assert firm.precision_mwm <= 0.01
        assert firm.simulation.max_deficit_mwm == 0.0
        # Over the 3 dry months (m=3,4,5) starting from full (1000):
        # Available = 1000 + 3*400 = 2200 -> max sustainable constant load = 2200 / 3 = 733.3333...
        assert math.isclose(firm.firm_energy_mwm, 2200.0 / 3.0, abs_tol=0.02)
        assert firm.simulation.critical_period is not None
        assert firm.simulation.critical_period.start_month == 3
        assert firm.simulation.critical_period.end_month == 5


class TestEconomicsAndHeatRate:
    def test_heat_rate_fuel_cost(self):
        # HeatRate = 2150 Kcal/MWh? Actually typical: 2,150,000 Kcal/MWh, PCI=10,000 Kcal/kg, P=0.50 USD/kg
        # C_comb = 2150000 * 0.50 / 10000 = 107.5 US$/MWh
        cost = calculate_fuel_cost_from_heat_rate(2_150_000.0, 0.50, 10_000.0)
        assert math.isclose(cost, 107.5, rel_tol=1e-9)

    def test_frc_and_annual_costs_and_screening(self):
        # i = 10%, n = 20 -> FRC = 0.1 * 1.1^20 / (1.1^20 - 1) = 0.11745962477...
        frc = calculate_frc(10.0, 20)
        expected_frc = (0.10 * (1.10**20)) / ((1.10**20) - 1.0)
        assert math.isclose(frc, expected_frc, rel_tol=1e-9)

        t = ThermalPlantInput(
            plant_id="t1",
            name="Gas1",
            fuel_type="GAS",
            installed_power_mw=500.0,
            fc_max=0.9,
            fc_min=0.0,
            fixed_cost_usd_kw=1000.0,
            variable_cost_usd_mwh=50.0,
            useful_life_years=20,
            guide_curve=[50.0] * 12,
        )
        econ = calculate_thermal_economics([t], {"t1": 200.0}, interest_rate_pct=10.0)[0]
        expected_cf = 1000.0 * 500_000.0 * expected_frc
        expected_cv = 200.0 * 50.0 * HOURS_PER_COMMERCIAL_YEAR
        assert math.isclose(econ.fixed_cost_usd_year, expected_cf, rel_tol=1e-9)
        assert math.isclose(econ.variable_cost_usd_year, expected_cv, rel_tol=1e-9)
        assert math.isclose(econ.total_cost_kusd_year, (expected_cf + expected_cv) / 1000.0, rel_tol=1e-9)

        curves = calculate_screening_curves([t], interest_rate_pct=10.0, steps=10)
        assert len(curves) == 1
        assert curves[0].points[0].hours == 0.0
        assert math.isclose(curves[0].points[0].total_cost_usd, expected_cf, rel_tol=1e-9)
        assert curves[0].points[-1].hours == HOURS_PER_COMMERCIAL_YEAR


class TestInflowParsers:
    def test_parse_vazoes_txt_13_columns(self):
        txt = (
            "ANO JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ\n"
            "2020 100 110 120 130 140 150 160 170 180 190 200 210\n"
        ).encode("utf-8")
        rows = parse_inflow_file(txt, "vazoes.txt")
        assert len(rows) == 12
        assert rows[0].year == 2020 and rows[0].month == 1 and rows[0].flow_m3s == 100.0
        assert rows[-1].month == 12 and rows[-1].flow_m3s == 210.0

    def test_rejects_oversized_file_and_formula_injection(self):
        with pytest.raises(ValueError, match="5 MB"):
            parse_inflow_file(b"0" * (MAX_INFLOW_FILE_SIZE_BYTES + 1), "vazoes.txt")

        malicious = b"2020 =CMD() 10 10 10 10 10 10 10 10 10 10 10\n"
        with pytest.raises(ValueError):
            parse_inflow_file(malicious, "vazoes.txt")

        assert sanitize_csv_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
        assert sanitize_csv_cell("NormalText") == "NormalText"
