"""Project CRUD and template cloning endpoints with strict RBAC/anti-IDOR."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authorized_project, get_current_user
from app.db.models import (
    Classroom,
    ClassroomMembership,
    HydroPlant,
    InflowSeries,
    Project,
    SimulationConfig,
    ThermalPlant,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.schemas import (
    ProjectCloneRequest,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    classroom_id: str | None = Query(default=None),
    include_student_projects: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """List projects visible to the current user.

    - ALUNO: sees own projects + templates of classrooms they belong to.
    - PROFESSOR: sees own projects + (optionally) all student projects in their classrooms.
    """
    if user.role == UserRole.PROFESSOR:
        owned_cls_ids_res = await db.execute(
            select(Classroom.id).where(Classroom.professor_id == user.id)
        )
        owned_cls_ids = list(owned_cls_ids_res.scalars().all())
        if include_student_projects and owned_cls_ids:
            cond = or_(
                Project.owner_id == user.id,
                Project.classroom_id.in_(owned_cls_ids),
            )
        else:
            cond = Project.owner_id == user.id
    else:
        mem_cls_ids_res = await db.execute(
            select(ClassroomMembership.classroom_id).where(
                ClassroomMembership.student_id == user.id
            )
        )
        mem_cls_ids = list(mem_cls_ids_res.scalars().all())
        if mem_cls_ids:
            cond = or_(
                Project.owner_id == user.id,
                (Project.is_template.is_(True) & Project.classroom_id.in_(mem_cls_ids)),
            )
        else:
            cond = Project.owner_id == user.id

    stmt = (
        select(Project, User.full_name)
        .join(User, User.id == Project.owner_id)
        .where(cond)
    )
    if classroom_id:
        stmt = stmt.where(Project.classroom_id == classroom_id)

    res = await db.execute(stmt.order_by(Project.updated_at.desc()))
    items: list[ProjectResponse] = []
    for proj, owner_name in res.all():
        item = ProjectResponse.model_validate(proj)
        item.owner_name = owner_name
        items.append(item)
    return items


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    if payload.is_template and user.role != UserRole.PROFESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas professores podem criar projetos-template.",
        )

    if payload.classroom_id:
        cls_res = await db.execute(
            select(Classroom).where(Classroom.id == payload.classroom_id)
        )
        classroom = cls_res.scalar_one_or_none()
        if classroom is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turma não encontrada.")
        if user.role == UserRole.PROFESSOR and classroom.professor_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não é o professor desta turma.")
        if user.role == UserRole.ALUNO:
            mem = await db.execute(
                select(ClassroomMembership).where(
                    ClassroomMembership.classroom_id == classroom.id,
                    ClassroomMembership.student_id == user.id,
                )
            )
            if mem.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não pertence a esta turma.")

    project = Project(
        name=payload.name.strip(),
        description=payload.description,
        owner_id=user.id,
        classroom_id=payload.classroom_id,
        is_template=payload.is_template,
    )
    db.add(project)
    await db.flush()

    # Create default simulation config
    db.add(SimulationConfig(project_id=project.id))
    await db.commit()
    await db.refresh(project)

    resp = ProjectResponse.model_validate(project)
    resp.owner_name = user.full_name
    return resp


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await get_authorized_project(project_id, user, db, require_write=False)
    owner_res = await db.execute(select(User.full_name).where(User.id == project.owner_id))
    resp = ProjectResponse.model_validate(project)
    resp.owner_name = owner_res.scalar_one_or_none()
    return resp


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await get_authorized_project(project_id, user, db, require_write=True)
    if payload.is_template is True and user.role != UserRole.PROFESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas professores podem marcar um projeto como template.",
        )

    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description
    if payload.is_template is not None:
        project.is_template = payload.is_template

    await db.commit()
    await db.refresh(project)
    resp = ProjectResponse.model_validate(project)
    resp.owner_name = user.full_name
    return resp


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await get_authorized_project(project_id, user, db, require_write=True)
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/clone", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def clone_project(
    project_id: str,
    payload: ProjectCloneRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Clone an authorized project (e.g. a classroom template) into the caller's private space."""
    source = await get_authorized_project(project_id, user, db, require_write=False)

    new_name = (
        payload.name.strip()
        if payload and payload.name
        else f"{source.name} (Cópia - {user.full_name.split()[0]})"
    )

    cloned = Project(
        name=new_name,
        description=source.description,
        owner_id=user.id,
        classroom_id=source.classroom_id,
        is_template=False,
    )
    db.add(cloned)
    await db.flush()

    # 1. Clone hydro plants in two passes to preserve downstream_plant_id DAG links
    src_hydros = list(
        (
            await db.execute(select(HydroPlant).where(HydroPlant.project_id == source.id))
        ).scalars().all()
    )
    id_map: dict[str, HydroPlant] = {}
    for h in src_hydros:
        new_h = HydroPlant(
            project_id=cloned.id,
            name=h.name,
            vmax_hm3=h.vmax_hm3,
            vmin_hm3=h.vmin_hm3,
            productivity_mw_m3s=h.productivity_mw_m3s,
            installed_power_mw=h.installed_power_mw,
            downstream_plant_id=None,
        )
        db.add(new_h)
        id_map[h.id] = new_h
    await db.flush()

    for h in src_hydros:
        if h.downstream_plant_id and h.downstream_plant_id in id_map:
            id_map[h.id].downstream_plant_id = id_map[h.downstream_plant_id].id
    await db.flush()

    # 2. Clone inflow series for each hydro plant
    for old_id, new_h in id_map.items():
        src_inflows = list(
            (
                await db.execute(
                    select(InflowSeries).where(InflowSeries.hydro_plant_id == old_id)
                )
            ).scalars().all()
        )
        db.add_all(
            [
                InflowSeries(
                    hydro_plant_id=new_h.id,
                    year=inf.year,
                    month=inf.month,
                    flow_m3s=inf.flow_m3s,
                    is_incremental=inf.is_incremental,
                )
                for inf in src_inflows
            ]
        )

    # 3. Clone thermal plants
    src_thermals = list(
        (
            await db.execute(
                select(ThermalPlant).where(ThermalPlant.project_id == source.id)
            )
        ).scalars().all()
    )
    db.add_all(
        [
            ThermalPlant(
                project_id=cloned.id,
                name=t.name,
                fuel_type=t.fuel_type,
                installed_power_mw=t.installed_power_mw,
                fc_max=t.fc_max,
                fc_min=t.fc_min,
                fixed_cost_usd_kw=t.fixed_cost_usd_kw,
                variable_cost_usd_mwh=t.variable_cost_usd_mwh,
                useful_life_years=t.useful_life_years,
                guide_curve=list(t.guide_curve),
                enabled=t.enabled,
            )
            for t in src_thermals
        ]
    )

    # 4. Clone simulation config
    src_cfg = (
        await db.execute(
            select(SimulationConfig).where(SimulationConfig.project_id == source.id)
        )
    ).scalar_one_or_none()
    if src_cfg:
        db.add(
            SimulationConfig(
                project_id=cloned.id,
                load_mwm=src_cfg.load_mwm,
                initial_earm_pct=src_cfg.initial_earm_pct,
                start_year=src_cfg.start_year,
                start_month=src_cfg.start_month,
                end_year=src_cfg.end_year,
                end_month=src_cfg.end_month,
                interest_rate_pct=src_cfg.interest_rate_pct,
                gh_max_mwm=src_cfg.gh_max_mwm,
            )
        )
    else:
        db.add(SimulationConfig(project_id=cloned.id))

    await db.commit()
    await db.refresh(cloned)

    resp = ProjectResponse.model_validate(cloned)
    resp.owner_name = user.full_name
    return resp
