import React, { useState } from "react";
import { Check, Copy, FileText, GraduationCap, Plus, Users } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDownloadBlob, apiFetch } from "@/lib/api";
import { Badge, Button, Card, CardHeader, Input } from "@/components/ui/primitives";
import { fmtNum } from "@/lib/palette";
import type { AuditRunSummary, Classroom, StudentMember } from "@/types/api";

interface ProfessorPageProps {
  classrooms: Classroom[];
  selectedClassroomId: string;
  onSelectClassroom: (id: string) => void;
  onOpenProject: (projectId: string) => void;
}

export function ProfessorPage({
  classrooms,
  selectedClassroomId,
  onSelectClassroom,
  onOpenProject,
}: ProfessorPageProps) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const activeClsId = selectedClassroomId || classrooms[0]?.id || "";

  const { data: members = [] } = useQuery({
    queryKey: ["classroom-members", activeClsId],
    queryFn: () => apiFetch<StudentMember[]>(`/classrooms/${activeClsId}/members`),
    enabled: Boolean(activeClsId),
  });

  const { data: auditRuns = [] } = useQuery({
    queryKey: ["classroom-audit", activeClsId],
    queryFn: () => apiFetch<AuditRunSummary[]>(`/classrooms/${activeClsId}/audit-runs`),
    enabled: Boolean(activeClsId),
  });

  const createClsMut = useMutation({
    mutationFn: () =>
      apiFetch<Classroom>("/classrooms", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      }),
    onSuccess: (created) => {
      setName("");
      setDescription("");
      qc.invalidateQueries({ queryKey: ["classrooms"] });
      onSelectClassroom(created.id);
    },
  });

  function copyCode(cls: Classroom) {
    navigator.clipboard.writeText(cls.invite_code);
    setCopiedId(cls.id);
    window.setTimeout(() => setCopiedId(null), 1500);
  }

  return (
    <div className="space-y-6">
      {/* Create Classroom */}
      <Card>
        <CardHeader
          title="Criar Nova Turma Acadêmica"
          description="Gere um código de convite automático para os alunos ingressarem e clonarem seus projetos-template"
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createClsMut.mutate();
          }}
          className="p-5 grid grid-cols-1 md:grid-cols-3 gap-3 items-end"
        >
          <div>
            <label className="text-xs font-medium">Nome da Turma</label>
            <Input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex.: SEP II — 2026.2"
            />
          </div>
          <div>
            <label className="text-xs font-medium">Descrição</label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Planejamento de sistemas hidrotérmicos"
            />
          </div>
          <div>
            <Button type="submit" disabled={createClsMut.isPending} className="w-full md:w-auto">
              <Plus className="h-4 w-4" /> Criar Turma
            </Button>
          </div>
        </form>
      </Card>

      {/* Classrooms Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {classrooms.map((cls) => (
          <Card
            key={cls.id}
            className={`p-4 cursor-pointer transition ${
              cls.id === activeClsId ? "ring-2 ring-sky-500" : ""
            }`}
          >
            <div onClick={() => onSelectClassroom(cls.id)}>
              <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-sm flex items-center gap-1.5">
                  <GraduationCap className="h-4 w-4 text-sky-600" />
                  {cls.name}
                </div>
                <Badge tone="sky">{cls.student_count} alunos</Badge>
              </div>
              {cls.description && (
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{cls.description}</p>
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-200">
                {cls.invite_code}
              </span>
              <Button size="sm" variant="ghost" onClick={() => copyCode(cls)}>
                {copiedId === cls.id ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" /> Copiado
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" /> Copiar
                  </>
                )}
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {/* Enrolled Students */}
      <Card>
        <CardHeader
          title="Alunos Matriculados na Turma"
          action={
            <Badge tone="emerald">
              <Users className="h-3 w-3 mr-1" /> {members.length} estudantes
            </Badge>
          }
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-xs text-slate-500">
                <th className="py-2.5 px-4 text-left">Aluno</th>
                <th className="py-2.5 px-4 text-left">E-mail</th>
                <th className="py-2.5 px-4 text-right">Cenários Criados</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {members.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-xs text-slate-500">
                    Nenhum aluno ingressou nesta turma ainda. Compartilhe o código de convite.
                  </td>
                </tr>
              ) : (
                members.map((m) => (
                  <tr key={m.id}>
                    <td className="py-2.5 px-4 font-medium">{m.full_name}</td>
                    <td className="py-2.5 px-4 text-slate-500">{m.email}</td>
                    <td className="py-2.5 px-4 text-right tabular-nums">{m.project_count}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Audit Log of Student Runs */}
      <Card>
        <CardHeader
          title="Auditoria de Simulações da Turma"
          description="Acompanhe os cenários executados pelos alunos, custos obtidos, déficits e exporte o PDF para correção"
        />
        <div className="overflow-x-auto">
          <table className="w-full text-xs tabular-nums">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500">
                <th className="py-2.5 px-4 text-left">Aluno</th>
                <th className="py-2.5 px-4 text-left">Projeto</th>
                <th className="py-2.5 px-4 text-left">Tipo</th>
                <th className="py-2.5 px-4 text-right">Custo Total (kUS$)</th>
                <th className="py-2.5 px-4 text-right">Déficit Máx</th>
                <th className="py-2.5 px-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {auditRuns.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500">
                    Nenhuma simulação registrada nesta turma.
                  </td>
                </tr>
              ) : (
                auditRuns.map((r) => (
                  <tr key={r.run_id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                    <td className="py-2 px-4 font-medium">{r.student_name}</td>
                    <td className="py-2 px-4">{r.project_name}</td>
                    <td className="py-2 px-4">
                      <Badge tone={r.run_type === "FIRM_ENERGY" ? "indigo" : "sky"}>
                        {r.run_type}
                      </Badge>
                    </td>
                    <td className="py-2 px-4 text-right">
                      {fmtNum(r.summary.total_cost_kusd_year, 1)}
                    </td>
                    <td className="py-2 px-4 text-right">
                      <span
                        className={
                          r.summary.max_deficit_mwm > 0
                            ? "text-red-600 font-semibold"
                            : "text-emerald-600"
                        }
                      >
                        {fmtNum(r.summary.max_deficit_mwm, 1)}
                      </span>
                    </td>
                    <td className="py-2 px-4 text-right space-x-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onOpenProject(r.project_id)}
                      >
                        Abrir
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          apiDownloadBlob(
                            `/projects/${r.project_id}/runs/${r.run_id}/report-pdf`,
                            `auditoria_${r.run_id.slice(0, 8)}.pdf`
                          )
                        }
                      >
                        <FileText className="h-3.5 w-3.5" /> PDF
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
