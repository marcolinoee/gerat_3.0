import React, { useState } from "react";
import { Zap, ShieldCheck, GraduationCap, BookOpen } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button, Card, Input, Select } from "@/components/ui/primitives";
import type { UserRole } from "@/types/api";

export function AuthPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("professor@gerat.local");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("ALUNO");
  const [inviteCode, setInviteCode] = useState("GERAT-2026");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register({
          email,
          full_name: fullName,
          password,
          role,
          invite_code: role === "ALUNO" && inviteCode.trim() ? inviteCode.trim() : undefined,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro na autenticação.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-sky-50/40 to-slate-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-sky-600 text-white shadow-md">
            <Zap className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            GERAT Web
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Planejamento Hidrotérmico — Reservatório Equivalente de Energia & Curva Guia
          </p>
        </div>

        <Card className="p-6">
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 p-1 mb-5">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`rounded-md py-1.5 text-sm font-medium transition ${
                mode === "login"
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400"
              }`}
            >
              Entrar
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setEmail("");
                setError(null);
              }}
              className={`rounded-md py-1.5 text-sm font-medium transition ${
                mode === "register"
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400"
              }`}
            >
              Criar Conta
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Nome Completo
                  </label>
                  <Input
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Ex.: Maria Oliveira"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Perfil Acadêmico
                  </label>
                  <Select
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                  >
                    <option value="ALUNO">Aluno (Ingresso em Turma)</option>
                    <option value="PROFESSOR">Professor (Gestor de Turmas)</option>
                  </Select>
                </div>
                {role === "ALUNO" && (
                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Código da Turma (opcional)
                    </label>
                    <Input
                      value={inviteCode}
                      onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                      placeholder="Ex.: GERAT-2026"
                    />
                  </div>
                )}
              </>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                E-mail Institucional
              </label>
              <Input
                type="text"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="professor@gerat.local"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Senha
              </label>
              <Input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 px-3 py-2 text-xs text-red-700 dark:text-red-300">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting
                ? "Autenticando..."
                : mode === "login"
                ? "Acessar Plataforma"
                : "Criar Conta e Entrar"}
            </Button>
          </form>

          <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 grid grid-cols-3 gap-2 text-center text-[11px] text-slate-500 dark:text-slate-400">
            <div className="flex flex-col items-center gap-1">
              <ShieldCheck className="h-4 w-4 text-sky-600" />
              <span>JWT + Cookie</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <GraduationCap className="h-4 w-4 text-emerald-600" />
              <span>Turmas RBAC</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <BookOpen className="h-4 w-4 text-indigo-600" />
              <span>PDF Vetorial</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
