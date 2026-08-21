import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, CheckCircle2, Clock, Handshake, Loader2, MessageSquare,
  Plus, Search, Trash2, Upload,
} from "lucide-react";
import { toast } from "sonner";
import { adminDashboard, AdminUser, Founder } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Programa de fundadores — Pro de graça em troca de uso e feedback.
 *
 * A tela é construída em volta de UMA pergunta: renovar ou não, quando o ciclo vencer.
 * Por isso mostra as três colunas do trato lado a lado — recebeu, usou, devolveu — em vez
 * de um painel de engajamento. Uso sozinho não responde: quem joga muito e nunca fala não
 * é o mesmo caso de quem joga e reporta, e tratar os dois igual é como o programa vira
 * doação sem ninguém decidir isso.
 */

function dataCurta(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function Indicador({ n, label, tom }: { n: number; label: string; tom: "bom" | "alerta" | "neutro" }) {
  return (
    <div className="rounded-lg border border-border bg-hud-surface px-4 py-3">
      <p
        className={cn(
          "font-mono text-2xl font-bold tabular-nums",
          tom === "bom" && "text-primary",
          tom === "alerta" && "text-amber-400",
          tom === "neutro" && "text-foreground",
        )}
      >
        {n}
      </p>
      <p className="mt-0.5 text-[11px] leading-tight text-muted-foreground">{label}</p>
    </div>
  );
}

/** Etiqueta do estado do trato. Três estados, nomeados pelo que significam para a decisão. */
function EstadoDoTrato({ f }: { f: Founder }) {
  if (f.honrando) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary ring-1 ring-primary/20">
        <CheckCircle2 className="size-3" /> Honrando
      </span>
    );
  }
  if (f.usou) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-400 ring-1 ring-amber-500/20">
        <MessageSquare className="size-3" /> Usa, não fala
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted/40 px-2 py-0.5 text-[10px] font-bold text-muted-foreground ring-1 ring-border">
      <AlertTriangle className="size-3" /> Silencioso
    </span>
  );
}

function Convidar({ onPronto }: { onPronto: () => void }) {
  const [busca, setBusca] = useState("");
  const [meses, setMeses] = useState(6);
  const [escolhidos, setEscolhidos] = useState<AdminUser[]>([]);

  // Sem filtro de papel DE PROPÓSITO. A primeira versão filtrava `role: "player"` e sumia
  // silenciosamente com contas admin/coach — buscar o próprio e-mail devolvia lista vazia
  // sem dizer por quê. Agora o papel aparece ao lado e quem opera decide.
  const { data, isFetching } = useQuery({
    queryKey: ["admin-users-founder-pick", busca],
    queryFn: () => adminDashboard.users({ search: busca, limit: 8 }),
    enabled: busca.trim().length >= 2,
    staleTime: 15_000,
  });

  const conceder = useMutation({
    mutationFn: () => adminDashboard.grantFounders(escolhidos.map((u) => u.id), meses),
    onSuccess: (r) => {
      toast.success(`${r.concedidos.length} fundador(es) até ${dataCurta(r.expira_em)}`);
      // Pulado NÃO é silêncio: assinante pagante é preservado de propósito, e quem
      // opera precisa saber que aquele nome não entrou.
      r.pulados?.forEach((p) =>
        toast.warning(`user ${p.user_id} não entrou: ${p.motivo}`, { duration: 8000 }));
      setEscolhidos([]);
      setBusca("");
      onPronto();
    },
    onError: (e: Error) => toast.error(e.message || "Não consegui conceder"),
  });

  const buscou = busca.trim().length >= 2;
  const achados = (data?.users ?? []).filter((u) => !escolhidos.some((e) => e.id === u.id));

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4">
      <h3 className="mb-3 flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary">
        <Plus className="size-3.5" /> Convidar fundadores
      </h3>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-[11px] text-muted-foreground">Buscar jogador</label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="nome ou email (2+ letras)"
              className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-[11px] text-muted-foreground">Duração</label>
          <select
            value={meses}
            onChange={(e) => setMeses(Number(e.target.value))}
            className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground focus:border-primary focus:outline-none"
          >
            <option value={3}>3 meses</option>
            <option value={6}>6 meses</option>
            <option value={12}>12 meses</option>
          </select>
        </div>
      </div>

      {isFetching && buscou && (
        <p className="mt-2 text-[11px] text-muted-foreground">buscando…</p>
      )}
      {/* Busca sem resultado precisa DIZER isso. Lista vazia e muda é indistinguível de
          "ainda carregando" — e foi assim que digitar um e-mail válido pareceu tela quebrada. */}
      {buscou && !isFetching && achados.length === 0 && (
        <div className="mt-2 rounded-md border border-border/60 bg-background/40 px-3 py-2.5 text-[11px] text-muted-foreground">
          Nenhuma conta encontrada para <span className="text-foreground">{busca.trim()}</span>.
          {" "}O fundador precisa <strong className="text-foreground">já ter conta</strong> no
          GrindLab. Se ele ainda não se cadastrou, mande o link de convite primeiro.
        </div>
      )}
      {achados.length > 0 && (
        <div className="mt-2 space-y-1">
          {achados.map((u) => (
            <button
              key={u.id}
              onClick={() => setEscolhidos((s) => [...s, u])}
              className="flex w-full items-center justify-between gap-2 rounded-md border border-border/60 px-3 py-1.5 text-left text-xs hover:border-primary/40 hover:bg-hud-elevated/40"
            >
              <span className="flex items-center gap-2">
                <span className="text-foreground">{u.username}</span>
                {u.role !== "player" && (
                  <span className="rounded-full bg-muted/40 px-1.5 py-0.5 text-[9px] font-bold uppercase text-muted-foreground">
                    {u.role}
                  </span>
                )}
              </span>
              <span className="truncate text-muted-foreground">{u.email}</span>
            </button>
          ))}
        </div>
      )}

      {escolhidos.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {escolhidos.map((u) => (
              <span
                key={u.id}
                className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] text-primary ring-1 ring-primary/20"
              >
                {u.username}
                <button
                  onClick={() => setEscolhidos((s) => s.filter((x) => x.id !== u.id))}
                  className="text-primary/70 hover:text-primary"
                  aria-label={`remover ${u.username}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <button
            onClick={() => conceder.mutate()}
            disabled={conceder.isPending}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow disabled:opacity-50"
          >
            {conceder.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Handshake className="size-3.5" />}
            Dar Pro a {escolhidos.length} por {meses} meses
          </button>
        </div>
      )}
    </div>
  );
}

export function FoundersTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-founders"],
    queryFn: adminDashboard.founders,
    staleTime: 30_000,
  });

  const revogar = useMutation({
    mutationFn: (uid: number) => adminDashboard.revokeFounder(uid),
    onSuccess: () => {
      toast.success("Fundador removido do programa");
      qc.invalidateQueries({ queryKey: ["admin-founders"] });
    },
    onError: (e: Error) => toast.error(e.message || "Não consegui remover"),
  });

  const recarrega = () => qc.invalidateQueries({ queryKey: ["admin-founders"] });

  // Ordem de leitura = ordem de ação: quem vence primeiro aparece primeiro.
  const lista = useMemo(() => {
    const fs = [...(data?.founders ?? [])];
    fs.sort((a, b) => (a.dias_restantes ?? 9999) - (b.dias_restantes ?? 9999));
    return fs;
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> carregando programa…
      </div>
    );
  }

  const r = data?.resumo;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Indicador n={r?.total ?? 0} label="fundadores no programa" tom="neutro" />
        <Indicador n={r?.honrando ?? 0} label="honrando o trato (usam e dão retorno)" tom="bom" />
        <Indicador n={r?.silenciosos ?? 0} label="nunca usaram nada" tom="alerta" />
        <Indicador n={r?.vencendo_em_30d ?? 0} label="vencem em 30 dias" tom="alerta" />
      </div>

      <Convidar onPronto={recarrega} />

      {lista.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-hud-surface/50 p-8 text-center">
          <Handshake className="mx-auto mb-3 size-8 text-muted-foreground/50" />
          <p className="text-sm font-semibold text-foreground">Nenhum fundador ainda</p>
          <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
            Convide jogadores acima. Eles ganham Pro pelo período escolhido, e esta tela passa
            a mostrar o que cada um usou e o que devolveu em feedback.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-hud-surface">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                <th className="px-4 py-3">Fundador</th>
                <th className="px-4 py-3">Trato</th>
                <th className="px-4 py-3 text-right">Recebeu até</th>
                <th className="px-4 py-3 text-right">Torneios</th>
                <th className="px-4 py-3 text-right">Dias treinados</th>
                <th className="px-4 py-3 text-right">Feedbacks</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {lista.map((f) => (
                <tr key={f.user_id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-foreground">{f.username}</p>
                    <p className="text-[11px] text-muted-foreground">{f.email}</p>
                  </td>
                  <td className="px-4 py-3"><EstadoDoTrato f={f} /></td>
                  <td className="px-4 py-3 text-right">
                    <p className="tabular-nums text-foreground">{dataCurta(f.expira_em)}</p>
                    {f.dias_restantes != null && (
                      <p
                        className={cn(
                          "text-[11px] tabular-nums",
                          f.dias_restantes < 0
                            ? "text-destructive"
                            : f.dias_restantes <= 30
                              ? "text-amber-400"
                              : "text-muted-foreground",
                        )}
                      >
                        {f.dias_restantes < 0
                          ? `venceu há ${Math.abs(f.dias_restantes)}d`
                          : `${f.dias_restantes}d restantes`}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <p className="tabular-nums text-foreground">{f.torneios}</p>
                    <p className="text-[11px] text-muted-foreground">
                      <Upload className="mr-0.5 inline size-2.5" />
                      {dataCurta(f.ultimo_import)}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-foreground">
                    {f.dias_treinados}
                    <span className="ml-1 text-[11px] text-muted-foreground">({f.treinos})</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <p
                      className={cn(
                        "tabular-nums",
                        f.feedbacks > 0 ? "font-semibold text-primary" : "text-muted-foreground",
                      )}
                    >
                      {f.feedbacks}
                    </p>
                    {f.ultimo_feedback && (
                      <p className="text-[11px] text-muted-foreground">
                        <Clock className="mr-0.5 inline size-2.5" />
                        {dataCurta(f.ultimo_feedback)}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => {
                        if (confirm(`Tirar ${f.username} do programa? A conta volta para o plano free.`)) {
                          revogar.mutate(f.user_id);
                        }
                      }}
                      className="rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      aria-label={`remover ${f.username}`}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        <strong className="text-foreground">Como ler:</strong> “Honrando” é quem importou mãos,
        voltou a treinar em dias diferentes <em>e</em> mandou algum retorno. “Usa, não fala”
        cumpre metade do trato — costuma ser quem só precisa ser perguntado. “Silencioso” nunca
        usou nada, e é o caso em que renovar não faz diferença.
      </p>
    </div>
  );
}
