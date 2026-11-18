"""Idempotent database seed for GERAT Web."""

from __future__ import annotations

import logging
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    Classroom,
    FuelType,
    HydroPlant,
    InflowSeries,
    Project,
    SimulationConfig,
    ThermalPlant,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

# Seasonal factors (Jan..Dec) typical of the São Francisco basin (wet summer, dry winter)
_SEASONAL_FACTORS = [
    1.55,  # Jan
    1.65,  # Fev
    1.50,  # Mar
    1.15,  # Abr
    0.82,  # Mai
    0.62,  # Jun
    0.50,  # Jul
    0.44,  # Ago
    0.42,  # Set
    0.52,  # Out
    0.85,  # Nov
    1.28,  # Dez
]

# Multi-year hydrological cycle (includes dry cycle 2017-2019 for critical period study)
_ANNUAL_FACTORS = {
    2015: 1.05,
    2016: 0.92,
    2017: 0.62,
    2018: 0.54,
    2019: 0.68,
    2020: 0.95,
    2021: 1.10,
    2022: 1.18,
    2023: 1.02,
    2024: 0.96,
}


async def run_seed(session: AsyncSession) -> None:
    """Create initial professor, demo classroom, and 5-plant São Francisco cascade template."""
    settings = get_settings()

    result = await session.execute(
        select(User).where(User.email == settings.SEED_ADMIN_EMAIL)
    )
    professor = result.scalar_one_or_none()

    if professor is None:
        if not settings.SEED_ADMIN_PASSWORD:
            logger.warning(
                "SEED_ADMIN_PASSWORD não configurada; pulando criação do usuário seed."
            )
            return

        professor = User(
            email=settings.SEED_ADMIN_EMAIL,
            full_name=settings.SEED_ADMIN_NAME,
            password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
            role=UserRole.PROFESSOR,
        )
        session.add(professor)
        await session.flush()
        logger.info("Usuário professor seed criado: %s", professor.email)

    # Demo classroom
    cls_res = await session.execute(
        select(Classroom).where(Classroom.invite_code == "GERAT-2026")
    )
    classroom = cls_res.scalar_one_or_none()
    if classroom is None:
        classroom = Classroom(
            name="Planejamento Hidrotérmico — Turma 2026",
            description="Turma demonstrativa para simulação de REE, Curva Guia e Sensibilidade Econômica.",
            invite_code="GERAT-2026",
            professor_id=professor.id,
        )
        session.add(classroom)
        await session.flush()

    # Template project (5-plant São Francisco cascade + 4 thermals)
    proj_res = await session.execute(
        select(Project).where(
            Project.classroom_id == classroom.id,
            Project.is_template.is_(True),
        )
    )
    if proj_res.scalar_one_or_none() is not None:
        await session.commit()
        return

    template = Project(
        name="Cascata São Francisco (Template Padrão)",
        description=(
            "Modelo didático com a cascata de 5 hidrelétricas do Rio São Francisco "
            "(Três Marias → Sobradinho → Itaparica → Complexo Paulo Afonso → Xingó) "
            "e parque térmico diversificado (Nuclear, Carvão, Gás e Óleo)."
        ),
        owner_id=professor.id,
        classroom_id=classroom.id,
        is_template=True,
    )
    session.add(template)
    await session.flush()

    # Build cascade from downstream to upstream so downstream_plant_id is already available
    xingo = HydroPlant(
        project_id=template.id,
        name="Xingó",
        vmax_hm3=3800.0,
        vmin_hm3=3700.0,
        productivity_mw_m3s=1.08,
        installed_power_mw=3162.0,
        downstream_plant_id=None,
    )
    session.add(xingo)
    await session.flush()

    paulo_afonso = HydroPlant(
        project_id=template.id,
        name="Complexo Paulo Afonso",
        vmax_hm3=1280.0,
        vmin_hm3=1100.0,
        productivity_mw_m3s=0.92,
        installed_power_mw=4279.0,
        downstream_plant_id=xingo.id,
    )
    session.add(paulo_afonso)
    await session.flush()

    itaparica = HydroPlant(
        project_id=template.id,
        name="Itaparica",
        vmax_hm3=10782.0,
        vmin_hm3=7234.0,
        productivity_mw_m3s=0.46,
        installed_power_mw=1479.0,
        downstream_plant_id=paulo_afonso.id,
    )
    session.add(itaparica)
    await session.flush()

    sobradinho = HydroPlant(
        project_id=template.id,
        name="Sobradinho",
        vmax_hm3=34116.0,
        vmin_hm3=5447.0,
        productivity_mw_m3s=0.25,
        installed_power_mw=1050.0,
        downstream_plant_id=itaparica.id,
    )
    session.add(sobradinho)
    await session.flush()

    tres_marias = HydroPlant(
        project_id=template.id,
        name="Três Marias",
        vmax_hm3=19528.0,
        vmin_hm3=4250.0,
        productivity_mw_m3s=0.45,
        installed_power_mw=396.0,
        downstream_plant_id=sobradinho.id,
    )
    session.add(tres_marias)
    await session.flush()

    # Deterministic natural inflow series (m3/s) for 2015-2024
    base_flows = [
        (tres_marias, 680.0),
        (sobradinho, 1850.0),
        (itaparica, 1920.0),
        (paulo_afonso, 1960.0),
        (xingo, 2000.0),
    ]
    inflow_rows: list[InflowSeries] = []
    for plant_idx, (plant, base_q) in enumerate(base_flows):
        for year, y_factor in _ANNUAL_FACTORS.items():
            for month in range(1, 13):
                s_factor = _SEASONAL_FACTORS[month - 1]
                # Small deterministic ripple for realistic variability
                ripple = 1.0 + 0.04 * math.sin((year * 12 + month + plant_idx) * 0.7)
                flow = round(base_q * y_factor * s_factor * ripple, 2)
                inflow_rows.append(
                    InflowSeries(
                        hydro_plant_id=plant.id,
                        year=year,
                        month=month,
                        flow_m3s=flow,
                        is_incremental=False,
                    )
                )
    session.add_all(inflow_rows)

    # 4 typical thermal plants
    thermals = [
        ThermalPlant(
            project_id=template.id,
            name="UTE Nuclear Base",
            fuel_type=FuelType.NUCLEAR,
            installed_power_mw=1350.0,
            fc_max=0.90,
            fc_min=0.80,
            fixed_cost_usd_kw=4500.0,
            variable_cost_usd_mwh=12.0,
            useful_life_years=40,
            guide_curve=[100.0] * 12,
            enabled=True,
        ),
        ThermalPlant(
            project_id=template.id,
            name="UTE Carvão Mineral",
            fuel_type=FuelType.COAL,
            installed_power_mw=1200.0,
            fc_max=0.85,
            fc_min=0.15,
            fixed_cost_usd_kw=2200.0,
            variable_cost_usd_mwh=42.0,
            useful_life_years=30,
            guide_curve=[65.0, 65.0, 60.0, 60.0, 55.0, 55.0, 60.0, 65.0, 70.0, 70.0, 70.0, 65.0],
            enabled=True,
        ),
        ThermalPlant(
            project_id=template.id,
            name="UTE Gás Natural CC",
            fuel_type=FuelType.GAS,
            installed_power_mw=1500.0,
            fc_max=0.90,
            fc_min=0.0,
            fixed_cost_usd_kw=1100.0,
            variable_cost_usd_mwh=78.0,
            useful_life_years=25,
            guide_curve=[45.0, 45.0, 45.0, 40.0, 40.0, 40.0, 45.0, 50.0, 50.0, 50.0, 50.0, 45.0],
            enabled=True,
        ),
        ThermalPlant(
            project_id=template.id,
            name="UTE Óleo Diesel Ponta",
            fuel_type=FuelType.OIL,
            installed_power_mw=800.0,
            fc_max=0.95,
            fc_min=0.0,
            fixed_cost_usd_kw=650.0,
            variable_cost_usd_mwh=185.0,
            useful_life_years=20,
            guide_curve=[25.0] * 12,
            enabled=True,
        ),
    ]
    session.add_all(thermals)

    sim_config = SimulationConfig(
        project_id=template.id,
        load_mwm=6200.0,
        initial_earm_pct=85.0,
        start_year=2015,
        start_month=1,
        end_year=2024,
        end_month=12,
        interest_rate_pct=10.0,
        gh_max_mwm=10366.0,
    )
    session.add(sim_config)

    await session.commit()
    logger.info("Seed inicial do GERAT Web concluído com sucesso.")
