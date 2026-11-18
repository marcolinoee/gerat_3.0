"""Integration and RBAC/anti-IDOR security tests for GERAT Web API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _register_and_token(
    client: AsyncClient,
    email: str,
    full_name: str,
    password: str,
    role: str = "ALUNO",
    invite_code: str | None = None,
) -> tuple[str, dict]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": full_name,
            "password": password,
            "role": role,
            "invite_code": invite_code,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["access_token"], data["user"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_auth_refresh_cookie_and_logout(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "prof1@gerat.local",
            "full_name": "Prof Um",
            "password": "StrongPassword123",
            "role": "PROFESSOR",
        },
    )
    assert resp.status_code == 201
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gerat_refresh_token=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "path=/api/v1/auth" in set_cookie.lower()

    # Refresh works with cookie
    ref = await client.post("/api/v1/auth/refresh")
    assert ref.status_code == 200
    assert ref.json()["access_token"]

    # Me works with Bearer token
    me = await client.get("/api/v1/auth/me", headers=_auth(ref.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "prof1@gerat.local"


@pytest.mark.asyncio
async def test_rbac_anti_idor_and_full_simulation_flow(client: AsyncClient):
    # 1. Professor registers and creates classroom + template
    prof_token, _ = await _register_and_token(
        client, "prof@uni.edu", "Prof. Silva", "ProfPass123", role="PROFESSOR"
    )
    cls_resp = await client.post(
        "/api/v1/classrooms",
        json={"name": "SEP II 2026", "description": "Turma de Planejamento"},
        headers=_auth(prof_token),
    )
    assert cls_resp.status_code == 201
    classroom = cls_resp.json()
    invite_code = classroom["invite_code"]

    tmpl_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Template Cascata",
            "classroom_id": classroom["id"],
            "is_template": True,
        },
        headers=_auth(prof_token),
    )
    assert tmpl_resp.status_code == 201
    template_id = tmpl_resp.json()["id"]

    # Add 2 hydro plants in cascade + inflows + 1 thermal plant
    u3 = (
        await client.post(
            f"/api/v1/projects/{template_id}/hydro-plants",
            json={
                "name": "Usina3",
                "vmax_hm3": 0.0,
                "vmin_hm3": 0.0,
                "productivity_mw_m3s": 0.98,
                "installed_power_mw": 1500.0,
            },
            headers=_auth(prof_token),
        )
    ).json()
    u2 = (
        await client.post(
            f"/api/v1/projects/{template_id}/hydro-plants",
            json={
                "name": "Usina2",
                "vmax_hm3": 5000.0,
                "vmin_hm3": 0.0,
                "productivity_mw_m3s": 0.80,
                "installed_power_mw": 1000.0,
                "downstream_plant_id": u3["id"],
            },
            headers=_auth(prof_token),
        )
    ).json()

    # Upload vazoes.txt to Usina2
    vazoes_txt = (
        "ANO JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ\n"
        "2023 1200 1300 1100 900 700 600 500 450 480 600 850 1100\n"
    ).encode("utf-8")
    up_resp = await client.post(
        f"/api/v1/projects/{template_id}/hydro-plants/{u2['id']}/inflows/upload",
        files={"file": ("vazoes.txt", vazoes_txt, "text/plain")},
        data={"is_incremental": "true"},
        headers=_auth(prof_token),
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["records_imported"] == 12

    # Add thermal plant
    t_resp = await client.post(
        f"/api/v1/projects/{template_id}/thermal-plants",
        json={
            "name": "UTE Carvao",
            "fuel_type": "COAL",
            "installed_power_mw": 500.0,
            "fc_max": 0.85,
            "fc_min": 0.10,
            "fixed_cost_usd_kw": 2000.0,
            "variable_cost_usd_mwh": 45.0,
            "useful_life_years": 25,
            "guide_curve": [60.0] * 12,
        },
        headers=_auth(prof_token),
    )
    assert t_resp.status_code == 201

    # Configure simulation horizon
    cfg_resp = await client.put(
        f"/api/v1/projects/{template_id}/config",
        json={
            "load_mwm": 1400.0,
            "initial_earm_pct": 80.0,
            "start_year": 2023,
            "start_month": 1,
            "end_year": 2023,
            "end_month": 12,
            "interest_rate_pct": 10.0,
        },
        headers=_auth(prof_token),
    )
    assert cfg_resp.status_code == 200

    # 2. Student A and Student B join the classroom
    stu_a_token, _ = await _register_and_token(
        client, "alunoA@uni.edu", "Aluno A", "PassA123", role="ALUNO", invite_code=invite_code
    )
    stu_b_token, _ = await _register_and_token(
        client, "alunoB@uni.edu", "Aluno B", "PassB123", role="ALUNO", invite_code=invite_code
    )

    # Student A cannot create a classroom (RBAC)
    forb_cls = await client.post(
        "/api/v1/classrooms",
        json={"name": "Turma Fake"},
        headers=_auth(stu_a_token),
    )
    assert forb_cls.status_code == 403

    # Student A cannot modify professor's template
    forb_tmpl = await client.patch(
        f"/api/v1/projects/{template_id}",
        json={"name": "Hacked"},
        headers=_auth(stu_a_token),
    )
    assert forb_tmpl.status_code == 403

    # Student A clones the template
    clone_resp = await client.post(
        f"/api/v1/projects/{template_id}/clone",
        json={"name": "Cenario Aluno A"},
        headers=_auth(stu_a_token),
    )
    assert clone_resp.status_code == 201
    proj_a_id = clone_resp.json()["id"]

    # Student A runs simulation & firm energy & sensitivity
    sim_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/simulate",
        headers=_auth(stu_a_token),
    )
    assert sim_resp.status_code == 200
    run_a_id = sim_resp.json()["id"]
    assert len(sim_resp.json()["monthly_results"]) == 12
    assert abs(sim_resp.json()["summary"]["ea_max_mwm"] - 3433.641975) < 1e-3

    firm_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/firm-energy",
        headers=_auth(stu_a_token),
    )
    assert firm_resp.status_code == 200
    assert firm_resp.json()["summary"]["max_deficit_mwm"] == 0.0

    sens_resp = await client.get(
        f"/api/v1/projects/{proj_a_id}/sensitivity?interest_rate_pct=12.0",
        headers=_auth(stu_a_token),
    )
    assert sens_resp.status_code == 200
    assert len(sens_resp.json()["series"]) == 1

    # 3. Anti-IDOR: Student B CANNOT view, simulate, edit, delete or export Student A's project
    assert (
        await client.get(f"/api/v1/projects/{proj_a_id}", headers=_auth(stu_b_token))
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/projects/{proj_a_id}/runs/{run_a_id}", headers=_auth(stu_b_token)
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/projects/{proj_a_id}/runs/{run_a_id}/export-csv",
            headers=_auth(stu_b_token),
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/projects/{proj_a_id}/runs/{run_a_id}/report-pdf",
            headers=_auth(stu_b_token),
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/projects/{proj_a_id}", headers=_auth(stu_b_token))
    ).status_code == 403

    # 4. Professor CAN audit Student A's project and classroom runs
    assert (
        await client.get(f"/api/v1/projects/{proj_a_id}", headers=_auth(prof_token))
    ).status_code == 200
    assert (
        await client.get(
            f"/api/v1/projects/{proj_a_id}/runs/{run_a_id}", headers=_auth(prof_token)
        )
    ).status_code == 200
    audit_resp = await client.get(
        f"/api/v1/classrooms/{classroom['id']}/audit-runs", headers=_auth(prof_token)
    )
    assert audit_resp.status_code == 200
    assert len(audit_resp.json()) >= 2
