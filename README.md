# GERAT Web — Planejamento Hidrotérmico (REE & Curva Guia)

Aplicação web full-stack moderna para ensino e simulação de planejamento da operação hidrotérmica de médio/longo prazo baseada no modelo de **Reservatório Equivalente de Energia (REE)** e despacho térmico por **Curva Guia**.

## Stack Tecnológica

- **Backend & Motor Matemático**: Python 3.12, FastAPI, Pydantic v2, NumPy, Pandas, SQLAlchemy 2.0 (async + `asyncpg`), Alembic, PostgreSQL 16, PyJWT + Argon2, WeasyPrint + Jinja2 + Matplotlib (OO `Figure()` + `Agg`).
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, TanStack Query, TanStack Table e Apache ECharts.
- **Infraestrutura**: Docker Multi-Stage Build (BuildKit) + Docker Compose + Nginx Unprivileged.

## Como Executar com Docker Compose

1. Copie o arquivo de variáveis de ambiente e ajuste as credenciais:

```bash
cp .env.example .env
```

2. Suba a aplicação completa (PostgreSQL 16 + Backend FastAPI + Frontend Nginx):

```bash
docker compose up -d --build
```

3. Acesse em: **http://localhost:8080**

- **Professor (Seed)**: `professor@gerat.local` (senha definida em `SEED_ADMIN_PASSWORD` no `.env`)
- **Código da Turma Demo (Alunos)**: `GERAT-2026`

## Testes Automatizados

```bash
docker exec gerat_backend pytest -v
```
