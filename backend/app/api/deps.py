"""FastAPI dependencies for authentication, RBAC, and anti-IDOR project access."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import Classroom, ClassroomMembership, Project, User, UserRole
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação ausente.",
        )

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido.",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
        )
    return user


async def require_professor(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.PROFESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a usuários com perfil PROFESSOR.",
        )
    return user


async def get_authorized_project(
    project_id: str,
    user: User,
    db: AsyncSession,
    *,
    require_write: bool = False,
) -> Project:
    """Enforce strict RBAC and anti-IDOR rules for project access.

    Rules:
    - Owner always has read + write access.
    - PROFESSOR has read access to any project in a classroom they own (for auditing).
    - Enrolled ALUNO has read-only access to `is_template=True` projects of their classroom.
    - All other access attempts return 403 Forbidden (or 404 if project doesn't exist).
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projeto não encontrado.",
        )

    # 1. Owner has full access
    if project.owner_id == user.id:
        return project

    if require_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para modificar este projeto.",
        )

    # 2. Professor auditing a project inside one of their classrooms
    if user.role == UserRole.PROFESSOR and project.classroom_id:
        cls_res = await db.execute(
            select(Classroom).where(
                Classroom.id == project.classroom_id,
                Classroom.professor_id == user.id,
            )
        )
        if cls_res.scalar_one_or_none() is not None:
            return project

    # 3. Student reading a classroom template (e.g. to inspect or clone)
    if project.is_template and project.classroom_id:
        mem_res = await db.execute(
            select(ClassroomMembership).where(
                ClassroomMembership.classroom_id == project.classroom_id,
                ClassroomMembership.student_id == user.id,
            )
        )
        if mem_res.scalar_one_or_none() is not None:
            return project

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado a este projeto.",
    )
