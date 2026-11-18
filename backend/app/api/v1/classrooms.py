"""Classroom management endpoints (RBAC: PROFESSOR creates/audits; ALUNO joins)."""

from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_professor
from app.db.models import (
    Classroom,
    ClassroomMembership,
    Project,
    SimulationRun,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.schemas import (
    AuditRunSummary,
    ClassroomCreate,
    ClassroomJoinRequest,
    ClassroomResponse,
    ProjectResponse,
    StudentMemberResponse,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


def _generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"GERAT-{code}"


@router.get("", response_model=list[ClassroomResponse])
async def list_classrooms(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClassroomResponse]:
    if user.role == UserRole.PROFESSOR:
        stmt = select(Classroom).where(Classroom.professor_id == user.id)
    else:
        stmt = (
            select(Classroom)
            .join(ClassroomMembership, ClassroomMembership.classroom_id == Classroom.id)
            .where(ClassroomMembership.student_id == user.id)
        )
    result = await db.execute(stmt.order_by(Classroom.created_at.desc()))
    classrooms = list(result.scalars().all())

    responses: list[ClassroomResponse] = []
    for cls in classrooms:
        cnt_res = await db.execute(
            select(func.count(ClassroomMembership.id)).where(
                ClassroomMembership.classroom_id == cls.id
            )
        )
        count = int(cnt_res.scalar() or 0)
        item = ClassroomResponse.model_validate(cls)
        item.student_count = count
        responses.append(item)

    return responses


@router.post("", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
async def create_classroom(
    payload: ClassroomCreate,
    professor: User = Depends(require_professor),
    db: AsyncSession = Depends(get_db),
) -> ClassroomResponse:
    invite_code = _generate_invite_code()
    # Ensure uniqueness
    while (
        await db.execute(select(Classroom).where(Classroom.invite_code == invite_code))
    ).scalar_one_or_none() is not None:
        invite_code = _generate_invite_code()

    classroom = Classroom(
        name=payload.name.strip(),
        description=payload.description,
        invite_code=invite_code,
        professor_id=professor.id,
    )
    db.add(classroom)
    await db.commit()
    await db.refresh(classroom)

    resp = ClassroomResponse.model_validate(classroom)
    resp.student_count = 0
    return resp


@router.post("/join", response_model=ClassroomResponse)
async def join_classroom(
    payload: ClassroomJoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassroomResponse:
    code = payload.invite_code.strip().upper()
    cls_res = await db.execute(select(Classroom).where(Classroom.invite_code == code))
    classroom = cls_res.scalar_one_or_none()
    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turma não encontrada para o código informado.",
        )

    if classroom.professor_id == user.id:
        resp = ClassroomResponse.model_validate(classroom)
        return resp

    existing = await db.execute(
        select(ClassroomMembership).where(
            ClassroomMembership.classroom_id == classroom.id,
            ClassroomMembership.student_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(ClassroomMembership(classroom_id=classroom.id, student_id=user.id))
        await db.commit()

    cnt_res = await db.execute(
        select(func.count(ClassroomMembership.id)).where(
            ClassroomMembership.classroom_id == classroom.id
        )
    )
    resp = ClassroomResponse.model_validate(classroom)
    resp.student_count = int(cnt_res.scalar() or 0)
    return resp


@router.get("/{classroom_id}/members", response_model=list[StudentMemberResponse])
async def list_classroom_members(
    classroom_id: str,
    professor: User = Depends(require_professor),
    db: AsyncSession = Depends(get_db),
) -> list[StudentMemberResponse]:
    cls_res = await db.execute(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.professor_id == professor.id,
        )
    )
    if cls_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turma não encontrada ou sem permissão.",
        )

    res = await db.execute(
        select(ClassroomMembership, User)
        .join(User, User.id == ClassroomMembership.student_id)
        .where(ClassroomMembership.classroom_id == classroom_id)
        .order_by(User.full_name)
    )
    members: list[StudentMemberResponse] = []
    for membership, student in res.all():
        proj_cnt = await db.execute(
            select(func.count(Project.id)).where(
                Project.owner_id == student.id,
                Project.classroom_id == classroom_id,
            )
        )
        members.append(
            StudentMemberResponse(
                id=student.id,
                email=student.email,
                full_name=student.full_name,
                joined_at=membership.joined_at,
                project_count=int(proj_cnt.scalar() or 0),
            )
        )
    return members


@router.get("/{classroom_id}/templates", response_model=list[ProjectResponse])
async def list_classroom_templates(
    classroom_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    # Verify membership or professor ownership
    cls_res = await db.execute(select(Classroom).where(Classroom.id == classroom_id))
    classroom = cls_res.scalar_one_or_none()
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turma não encontrada.")

    if classroom.professor_id != user.id:
        mem_res = await db.execute(
            select(ClassroomMembership).where(
                ClassroomMembership.classroom_id == classroom_id,
                ClassroomMembership.student_id == user.id,
            )
        )
        if mem_res.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não pertence a esta turma.")

    res = await db.execute(
        select(Project, User.full_name)
        .join(User, User.id == Project.owner_id)
        .where(Project.classroom_id == classroom_id, Project.is_template.is_(True))
        .order_by(Project.created_at.desc())
    )
    items: list[ProjectResponse] = []
    for proj, owner_name in res.all():
        item = ProjectResponse.model_validate(proj)
        item.owner_name = owner_name
        items.append(item)
    return items


@router.get("/{classroom_id}/audit-runs", response_model=list[AuditRunSummary])
async def audit_classroom_runs(
    classroom_id: str,
    professor: User = Depends(require_professor),
    db: AsyncSession = Depends(get_db),
) -> list[AuditRunSummary]:
    cls_res = await db.execute(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.professor_id == professor.id,
        )
    )
    if cls_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turma não encontrada.")

    res = await db.execute(
        select(SimulationRun, Project, User)
        .join(Project, Project.id == SimulationRun.project_id)
        .join(User, User.id == Project.owner_id)
        .where(Project.classroom_id == classroom_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(100)
    )
    audits: list[AuditRunSummary] = []
    for run, project, owner in res.all():
        audits.append(
            AuditRunSummary(
                run_id=run.id,
                project_id=project.id,
                project_name=project.name,
                student_id=owner.id,
                student_name=owner.full_name,
                student_email=owner.email,
                run_type=run.run_type,
                created_at=run.created_at,
                summary=run.summary,
            )
        )
    return audits
