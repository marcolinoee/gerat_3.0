import React, { useEffect, useState } from "react";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  CopyPlus,
  Droplets,
  FileText,
  Flame,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Moon,
  Play,
  Plus,
  Sliders,
  Sun,
  TrendingUp,
  Waves,
  Zap,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { apiDownloadBlob, apiFetch } from "@/lib/api";
import { AuthPage } from "@/pages/AuthPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { HydroPage } from "@/pages/HydroPage";
import { InflowsPage } from "@/pages/InflowsPage";
import { ThermalPage } from "@/pages/ThermalPage";
import { SimulationPage } from "@/pages/SimulationPage";
import { SensitivityPage } from "@/pages/SensitivityPage";
import { ProfessorPage } from "@/pages/ProfessorPage";
import { Badge, Button, Input, Select } from "@/components/ui/primitives";
import type { Classroom, Project, SimulationRun, ThermalPlant } from "@/types/api";

type NavKey =
  | "dashboard"
  | "hydro"
  | "inflows"
  | "thermal"
  | "simulation"
  | "sensitivity"
  | "professor";

export function App() {
  const { user, loading, logout } = useAuth();
  const qc = useQueryClient();

  const [dark, setDark] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [nav, setNav] = useState<NavKey>("dashboard");
  const [selectedClassroomId, setSelectedClassroomId] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [activeRun, setActiveRun] = useState<SimulationRun | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [showNewProj, setShowNewProj] = useState(false);
  const [newProjName, setNewProjName] = useState("");
  const [newProjTemplate, setNewProjTemplate] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const { data: classrooms = [] } = useQuery({
    queryKey: ["classrooms"],
    queryFn: () => apiFetch<Classroom[]>("/classrooms"),
    enabled: Boolean(user),
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["projects", user?.role],
    queryFn: () =>
      apiFetch<Project[]>(
        `/projects?include_student_projects=${user?.role === "PROFESSOR" ? "true" : "false"}`
      ),
    enabled: Boolean(user),
  });

  useEffect(() => {
    if (!selectedClassroomId && classrooms.length > 0) {
      setSelectedClassroomId(classrooms[0].id);
    }
  }, [classrooms, selectedClassroomId]);

  useEffect(() => {
    if (projects.length > 0 && !projects.some((p) => p.id === selectedProjectId)) {
      setSelectedProjectId(projects[0].id);
      setActiveRun(null);
    }
  }, [projects, selectedProjectId]);

  const currentProject = projects.find((p) => p.id === selectedProjectId) ?? null;
  const isReadOnly = Boolean(currentProject && user && currentProject.owner_id !== user.id);

  const { data: thermalPlants = [] } = useQuery({
    queryKey: ["thermals", selectedProjectId],
    queryFn: () => apiFetch<ThermalPlant[]>(`/projects/${selectedProjectId}/thermal-plants`),
    enabled: Boolean(selectedProjectId),
  });

  const { data: runs = [] } = useQuery({
    queryKey: ["runs", selectedProjectId],
    queryFn: () => apiFetch<SimulationRun[]>(`/projects/${selectedProjectId}/runs`),
    enabled: Boolean(selectedProjectId),
  });

  useEffect(() => {
    if (!selectedProjectId) return;
    if (runs.length > 0 && (!activeRun || activeRun.project_id !== selectedProjectId)) {
      apiFetch<SimulationRun>(`/projects/${selectedProjectId}/runs/${runs[0].id}`)
        .then(setActiveRun)
        .catch(() => {});
    }
  }, [runs, selectedProjectId]);

  const quickSimMut = useMutation({
    mutationFn: () =>
      apiFetch<SimulationRun>(`/projects/${selectedProjectId}/simulate`, { method: "POST" }),
    onSuccess: (run) => {
      setActiveRun(run);
      qc.invalidateQueries({ queryKey: ["runs", selectedProjectId] });
    },
  });

  const cloneMut = useMutation({
    mutationFn: (projId: string) =>
      apiFetch<Project>(`/projects/${projId}/clone`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (cloned) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setSelectedProjectId(cloned.id);
      setActiveRun(null);
    },
  });

  const createProjMut = useMutation({
    mutationFn: () =>
      apiFetch<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({
          name: newProjName,
          classroom_id: selectedClassroomId || null,
          is_template: user?.role === "PROFESSOR" ? newProjTemplate : false,
        }),
      }),
    onSuccess: (created) => {
      setNewProjName("");
      setShowNewProj(false);
      qc.invalidateQueries({ queryKey: ["projects"] });
      setSelectedProjectId(created.id);
      setActiveRun(null);
    },
  });

  const joinClsMut = useMutation({
    mutationFn: () =>
      apiFetch<Classroom>("/classrooms/join", {
        method: "POST",
        body: JSON.stringify({ invite_code: joinCode }),
      }),
    onSuccess: () => {
      setJoinCode("");
      qc.invalidateQueries({ queryKey: ["classrooms"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">
        Carregando GERAT Web...
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  const navItems: { key: NavKey; label: string; icon: React.ReactNode; profOnly?: boolean }[] = [
    { key: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
    { key: "hydro", label: "Hidrelétricas & REE", icon: <Droplets className="h-4 w-4" /> },
    { key: "inflows", label: "Séries de Vazões", icon: <Waves className="h-4 w-4" /> },
    { key: "thermal", label: "Térmicas & Curva Guia", icon: <Flame className="h-4 w-4" /> },
    { key: "simulation", label: "Simulação & Tabela", icon: <Sliders className="h-4 w-4" /> },
    { key: "sensitivity", label: "Sensibilidade", icon: <TrendingUp className="h-4 w-4" /> },
    {
      key: "professor",
      label: "Painel do Professor",
      icon: <GraduationCap className="h-4 w-4" />,
      profOnly: true,
    },
  ];

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      {/* Collapsible Sidebar */}
      <aside
        className={`${
          collapsed ? "w-16" : "w-64"
        } shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col transition-all duration-200`}
      >
        <div className="h-14 flex items-center justify-between px-3 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="h-8 w-8 rounded-lg bg-sky-600 text-white flex items-center justify-center shrink-0">
              <Zap className="h-4 w-4" />
            </div>
            {!collapsed && (
              <div className="truncate">
                <div className="text-sm font-bold leading-tight">GERAT Web</div>
                <div className="text-[10px] text-slate-500">REE & Curva Guia</div>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="p-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Alternar barra lateral"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {navItems
            .filter((item) => !item.profOnly || user.role === "PROFESSOR")
            .map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setNav(item.key)}
                className={`w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                  nav === item.key
                    ? "bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                {item.icon}
                {!collapsed && <span className="truncate">{item.label}</span>}
              </button>
            ))}
        </nav>

        {/* Student Quick Join */}
        {!collapsed && user.role === "ALUNO" && (
          <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
            <div className="text-[11px] font-medium text-slate-500">Ingressar em Turma</div>
            <div className="flex gap-1.5">
              <Input
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="GERAT-2026"
                className="h-8 text-xs"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={() => joinClsMut.mutate()}
                disabled={!joinCode.trim() || joinClsMut.isPending}
              >
                OK
              </Button>
            </div>
          </div>
        )}

        {/* User Footer */}
        <div className="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-xs font-semibold truncate">{user.full_name}</div>
              <Badge tone={user.role === "PROFESSOR" ? "indigo" : "emerald"} className="mt-0.5 text-[10px]">
                {user.role}
              </Badge>
            </div>
          )}
          <button
            type="button"
            onClick={() => logout()}
            title="Sair"
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="h-14 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Select
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                setActiveRun(null);
              }}
              className="max-w-xs h-8 text-xs"
            >
              {projects.length === 0 && <option value="">Sem projetos disponíveis</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.is_template ? "[TEMPLATE] " : ""}
                  {p.name}
                </option>
              ))}
            </Select>

            <Button size="sm" variant="outline" onClick={() => setShowNewProj((s) => !s)}>
              <Plus className="h-3.5 w-3.5" /> Novo
            </Button>

            {currentProject && currentProject.is_template && isReadOnly && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => cloneMut.mutate(currentProject.id)}
                disabled={cloneMut.isPending}
              >
                <CopyPlus className="h-3.5 w-3.5" /> Clonar para meu Espaço
              </Button>
            )}

            {isReadOnly && <Badge tone="amber">Somente Leitura</Badge>}
          </div>

          <div className="flex items-center gap-2">
            {selectedProjectId && (
              <>
                <Button
                  size="sm"
                  onClick={() => quickSimMut.mutate()}
                  disabled={quickSimMut.isPending}
                >
                  <Play className="h-3.5 w-3.5" />
                  {quickSimMut.isPending ? "Simulando..." : "Executar Simulação"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!activeRun}
                  onClick={() => {
                    if (!activeRun) return;
                    apiDownloadBlob(
                      `/projects/${selectedProjectId}/runs/${activeRun.id}/report-pdf`,
                      `relatorio_gerat_${activeRun.id.slice(0, 8)}.pdf`
                    );
                  }}
                >
                  <FileText className="h-3.5 w-3.5" /> Exportar PDF
                </Button>
              </>
            )}

            <button
              type="button"
              onClick={() => setDark((d) => !d)}
              className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Alternar tema claro/escuro"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </header>

        {/* Inline New Project Bar */}
        {showNewProj && (
          <div className="border-b border-slate-200 dark:border-slate-800 bg-sky-50/50 dark:bg-slate-900/70 px-4 py-3 flex flex-wrap items-center gap-3">
            <Input
              value={newProjName}
              onChange={(e) => setNewProjName(e.target.value)}
              placeholder="Nome do novo cenário hidrotérmico..."
              className="max-w-sm h-8 text-xs"
            />
            {user.role === "PROFESSOR" && (
              <label className="inline-flex items-center gap-1.5 text-xs">
                <input
                  type="checkbox"
                  checked={newProjTemplate}
                  onChange={(e) => setNewProjTemplate(e.target.checked)}
                />
                Publicar como Template da Turma
              </label>
            )}
            <Button
              size="sm"
              onClick={() => createProjMut.mutate()}
              disabled={!newProjName.trim() || createProjMut.isPending}
            >
              Criar Projeto
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowNewProj(false)}>
              Cancelar
            </Button>
          </div>
        )}

        {/* Main Workspace */}
        <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
          {nav === "professor" && user.role === "PROFESSOR" ? (
            <ProfessorPage
              classrooms={classrooms}
              selectedClassroomId={selectedClassroomId}
              onSelectClassroom={setSelectedClassroomId}
              onOpenProject={(pid) => {
                setSelectedProjectId(pid);
                setActiveRun(null);
                setNav("dashboard");
              }}
            />
          ) : !selectedProjectId ? (
            <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-12 text-center space-y-3">
              <Activity className="h-8 w-8 mx-auto text-slate-400" />
              <h2 className="text-base font-semibold">Nenhum projeto selecionado</h2>
              <p className="text-sm text-slate-500">
                Crie um novo cenário ou ingresse em uma turma (código <strong>GERAT-2026</strong>) para clonar o template do São Francisco.
              </p>
            </div>
          ) : nav === "dashboard" ? (
            <DashboardPage
              latestRun={activeRun}
              thermalPlants={thermalPlants}
              dark={dark}
              onRunSimulation={() => quickSimMut.mutate()}
              running={quickSimMut.isPending}
            />
          ) : nav === "hydro" ? (
            <HydroPage projectId={selectedProjectId} readOnly={isReadOnly} />
          ) : nav === "inflows" ? (
            <InflowsPage projectId={selectedProjectId} readOnly={isReadOnly} dark={dark} />
          ) : nav === "thermal" ? (
            <ThermalPage projectId={selectedProjectId} readOnly={isReadOnly} />
          ) : nav === "simulation" ? (
            <SimulationPage
              projectId={selectedProjectId}
              readOnly={isReadOnly}
              latestRun={activeRun}
              onRunCompleted={(run) => {
                setActiveRun(run);
                qc.invalidateQueries({ queryKey: ["runs", selectedProjectId] });
              }}
            />
          ) : (
            <SensitivityPage projectId={selectedProjectId} dark={dark} />
          )}
        </main>
      </div>
    </div>
  );
}
export default App;
