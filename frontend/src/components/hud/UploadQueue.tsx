import { useReducer, useEffect, useRef, useCallback, createContext, useContext } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { EVENTO_LOTE, invalidarAposImport } from "@/lib/refreshOnImport";
import { useTranslation, Trans } from "react-i18next";
import { CheckCircle2, AlertTriangle, Clock, Loader2, X, UploadCloud, Info } from "lucide-react";
import { tournaments, metrics } from "@/lib/api";
import { mensagemDeErroDeUpload } from "@/lib/mensagemDeUpload";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

type QueueStatus = "queued" | "processing" | "done" | "error";

interface QueueItem {
  id: string;
  name: string;
  status: QueueStatus;
  error?: string;
  note?: string;   // mensagem positiva (ex.: summary complementado) — não é erro
  /** Recibo do backend. Presente quando o arquivo JA ESTA GUARDADO no servidor: dali em diante
   *  fechar a aba nao perde nada, e a tela so acompanha o processamento. */
  recibo?: number;
}

type Action =
  | { type: "ADD"; items: QueueItem[] }
  | { type: "SET_STATUS"; id: string; status: QueueStatus; error?: string; note?: string }
  | { type: "SET_RECIBO"; id: string; recibo: number; note?: string }
  | { type: "DISMISS"; id: string }
  | { type: "CLEAR_DONE" };

function reducer(state: QueueItem[], action: Action): QueueItem[] {
  switch (action.type) {
    case "ADD":       return [...state, ...action.items];
    case "SET_STATUS": return state.map((i) => i.id === action.id ? { ...i, status: action.status, error: action.error, note: action.note } : i);
    // O recibo NAO apaga a nota nem o erro anteriores de proposito: ele so acrescenta o
    // "esta guardado" ao item, e a fase de acompanhamento e que decide o desfecho.
    case "SET_RECIBO": return state.map((i) => i.id === action.id ? { ...i, status: "processing", recibo: action.recibo, note: action.note ?? i.note } : i);
    case "DISMISS":   return state.filter((i) => i.id !== action.id);
    case "CLEAR_DONE": return state.filter((i) => i.status !== "done");
    default:          return state;
  }
}

// ── Status UI ─────────────────────────────────────────────────────────────────

const STATUS_ICON: Record<QueueStatus, React.ReactNode> = {
  queued:     <Clock className="size-3.5 text-muted-foreground" />,
  processing: <Loader2 className="size-3.5 text-amber-400 animate-spin" />,
  done:       <CheckCircle2 className="size-3.5 text-primary" />,
  error:      <AlertTriangle className="size-3.5 text-destructive" />,
};

// CHAVES, não texto: o rótulo é resolvido na render, com o idioma do usuário.
const STATUS_KEY: Record<QueueStatus, string> = {
  queued:     "uploadQueue.statusQueued",
  processing: "uploadQueue.statusProcessing",
  done:       "uploadQueue.statusDone",
  error:      "uploadQueue.statusError",
};

const STATUS_COLOR: Record<QueueStatus, string> = {
  queued:     "text-muted-foreground",
  processing: "text-amber-400",
  done:       "text-primary",
  error:      "text-destructive",
};

// ── Queue panel ────────────────────────────────────────────────────────────────

function QueuePanel({
  items,
  onDismiss,
  onClearDone,
}: {
  items: QueueItem[];
  onDismiss: (id: string) => void;
  onClearDone: () => void;
}) {
  const { t } = useTranslation("common");
  const pending = items.filter((i) => i.status === "queued" || i.status === "processing").length;
  const anyDone = items.some((i) => i.status === "done");
  const anyError = items.some((i) => i.status === "error");
  // Cabeçalho coerente com o resultado: não dizer "concluída" quando tudo falhou (a msg não condiz).
  const headerLabel = pending > 0
    ? t("uploadQueue.importing", { count: items.length })
    : anyDone
      ? (anyError ? t("uploadQueue.doneWithWarnings") : t("uploadQueue.done"))
      : t("uploadQueue.failed");

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-xl border border-border bg-background shadow-2xl">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2">
          <UploadCloud className="size-3.5 text-primary" />
          <span className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">
            {headerLabel}
          </span>
        </div>
        {pending === 0 && (
          <button
            onClick={onClearDone}
            className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          >
            {t("uploadQueue.close")}
          </button>
        )}
      </div>

      <ul className="max-h-64 overflow-y-auto divide-y divide-border">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
            {STATUS_ICON[item.status]}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground truncate font-medium leading-tight">{item.name}</p>
              <p className={cn("font-mono text-[10px] mt-0.5", STATUS_COLOR[item.status])}>
                {item.note ?? item.error ?? t(STATUS_KEY[item.status])}
              </p>
            </div>
            {(item.status === "done" || item.status === "error") && (
              <button
                onClick={() => onDismiss(item.id)}
                className="text-muted-foreground hover:text-foreground shrink-0 transition-colors"
                aria-label={t("uploadQueue.remove")}
              >
                <X className="size-3" />
              </button>
            )}
          </li>
        ))}
      </ul>

      {/* Aviso pós-import: o solver GTO processa as mãos em segundo plano e pode demorar. Só quando
          houve import de MÃOS (item done sem note) — summary complementado não gera análise GTO. */}
      {pending === 0 && items.some((i) => i.status === "done" && !i.note) && (
        <div className="flex items-start gap-2 border-t border-border bg-primary/[0.05] px-4 py-2.5">
          <Info className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
          <p className="text-[11px] leading-snug text-muted-foreground">
            <Trans i18nKey="uploadQueue.gtoNotice" ns="common"
              components={{ 1: <span className="text-foreground" />,
                            2: <span className="font-mono text-primary" /> }} />
          </p>
        </div>
      )}
    </div>
  );
}

// ── Provider GLOBAL ────────────────────────────────────────────────────────────
// A fila vive no topo do App (nunca desmonta), então o painel de upload SOBREVIVE à navegação:
// o usuário sobe vários torneios, troca de menu, e continua vendo o progresso/conclusão. Antes a
// fila vivia no componente (HudHeader/EmptyDashboard) e sumia ao trocar de página.

interface UploadQueueValue {
  enqueue: (files: FileList | File[]) => void;
}

const UploadQueueContext = createContext<UploadQueueValue>({ enqueue: () => {} });

export function useUploadQueue(): UploadQueueValue {
  return useContext(UploadQueueContext);
}

type RespostaDeUpload = {
  torneios_no_arquivo?: number;
  tambem_importados?: Array<{ status: number; duplicate?: boolean }>;
} | null | undefined;

/** Quantos torneios o arquivo trouxe, e o que aconteceu com cada um.
 *
 * Uma funcao so porque a resposta serve a DUAS coisas que precisam concordar: a frase na fila e
 * o XP. Se cada uma contasse por si, a tela diria "6 novos" e o contador somaria 36 (regra 5).
 *
 * "Ja estava no historico" NAO e falha, e e o caso NORMAL da sala que motivou tudo isto: o
 * export do PartyPoker e por intervalo de datas, entao quem reexporta uma semana reenvia a
 * anterior inteira. Chamar isso de "ficou de fora" faz o jogador procurar dado que nao falta —
 * achado na homologacao, com upload repetido contra o Postgres.
 */
export function contagemDoArquivo(r: RespostaDeUpload) {
  const n = r?.torneios_no_arquivo ?? 1;
  const demais = r?.tambem_importados ?? [];
  const ja = demais.filter((o) => o.duplicate).length;
  const fora = demais.filter((o) => o.status !== 200 && !o.duplicate).length;
  return { n, ja, fora, ok: n - ja - fora };
}

/** O recibo do upload assincrono na MESMA forma que `contagemDoArquivo` devolve.
 *
 * Existe para a frase da fila continuar saindo de `notaDeVariosTorneios`, com a copy que ja
 * esta nas tres locales e ja passou pelo revisor. A alternativa era escrever uma segunda
 * familia de frases para dizer a mesma coisa por outro caminho, que e como duas telas comecam
 * a discordar sobre o mesmo arquivo.
 */
export function contagemDoRecibo(r: {
  torneios_no_arquivo: number | null;
  torneios_gravados: number;
  torneios_ja_estavam: number;
  torneios_com_erro: number;
}) {
  const n = r.torneios_no_arquivo ?? 1;
  return { n, ja: r.torneios_ja_estavam, fora: r.torneios_com_erro, ok: r.torneios_gravados };
}

/** A nota que a fila mostra quando UM arquivo virou VARIOS torneios.
 *
 * O export do PartyPoker e por intervalo de datas, nao por torneio: um arquivo real de fundador
 * tem 36 torneios. O backend divide sozinho (`_analyze_orquestrado`), e sem esta frase o jogador
 * sobe um arquivo, ve 12 linhas novas na lista e nao sabe de onde vieram — nem se alguma ficou
 * de fora. `undefined` no caso comum (um torneio so): nota vazia e melhor que nota obvia.
 *
 * Funcao pura e exportada de proposito: a decisao mora fora do componente para poder ser testada
 * sem montar a fila inteira, que e onde bug de vitrine costuma se esconder.
 */
export function notaDeVariosTorneios(
  r: RespostaDeUpload,
  t: (k: string, o?: Record<string, unknown>) => string,
): string | undefined {
  return notaDaContagem(contagemDoArquivo(r), t);
}

/** A mesma frase, a partir da CONTAGEM. Os dois caminhos (resposta sincrona e recibo) chegam
 *  aqui, entao a frase nao pode divergir entre eles. */
export function notaDaContagem(
  { n, ok, ja, fora }: { n: number; ok: number; ja: number; fora: number },
  t: (k: string, o?: Record<string, unknown>) => string,
): string | undefined {
  if (n <= 1) return undefined;
  if (fora > 0) {
    return ja > 0
      ? t("uploadQueue.variosTorneiosMisto", { n, ok, ja, fora })
      : t("uploadQueue.variosTorneiosParcial", { n, ok, fora });
  }
  return ja > 0
    ? t("uploadQueue.variosTorneiosJaEstavam", { n, ok, ja })
    : t("uploadQueue.variosTorneios", { n });
}

export function UploadQueueProvider({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation("common");
  const [queue, dispatch] = useReducer(reducer, []);
  const fileMap    = useRef<Map<string, File>>(new Map());
  const processing = useRef(false);

  const enqueue = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files);
    if (arr.length === 0) return;

    const items: QueueItem[] = arr.map((f, i) => {
      const id = `${Date.now()}-${i}-${f.name}`;
      fileMap.current.set(id, f);
      return { id, name: f.name, status: "queued" as QueueStatus };
    });

    dispatch({ type: "ADD", items });
  }, []);

  // ── Recarga do LOTE ─────────────────────────────────────────────────────────────────────────
  //
  // Dispara UMA vez quando a fila esvazia, e não por arquivo. Duas razões, as duas medidas:
  //
  //   · corretude — quatro chaves derivadas de torneio (`bankroll-evolution`,
  //     `progression-status`, `proximo-passo`, `training-daily-status`) viviam em componentes que
  //     buscam por conta própria e não escutavam nada. Quem subia um torneio e ficava na tela via
  //     o gráfico de banca parado. Ver `lib/refreshOnImport`.
  //   · custo — um ciclo completo do dashboard custa ~17s de backend (três endpoints levam de 3 a
  //     5s cada). Em 28/07 houve 14 uploads: por arquivo seriam 14 ciclos.
  //
  // O `leaklab:tournament-imported` (por arquivo) continua existindo para quem quer saber de cada
  // import, como a lista de torneios.
  const qc = useQueryClient();
  const tinhaFila = useRef(false);
  useEffect(() => {
    const emAndamento = queue.some((i) => i.status === "queued" || i.status === "processing");
    const importou = queue.some((i) => i.status === "done");
    if (emAndamento) {
      tinhaFila.current = true;
      return;
    }
    if (tinhaFila.current && importou) {
      tinhaFila.current = false;
      invalidarAposImport(qc);
      window.dispatchEvent(new CustomEvent(EVENTO_LOTE));
    }
  }, [queue, qc]);

  const dismiss   = useCallback((id: string) => { fileMap.current.delete(id); dispatch({ type: "DISMISS", id }); }, []);
  const clearDone = useCallback(() => { queue.forEach((i) => { if (i.status === "done") fileMap.current.delete(i.id); }); dispatch({ type: "CLEAR_DONE" }); }, [queue]);

  // ── FASE 1: RECEBER ────────────────────────────────────────────────────────────────────
  // Manda o arquivo e para. Nao espera processar, e essa e a mudanca inteira: a requisicao
  // agora e curta, entao o timeout de 120s do servidor (que em producao chegou a 117,4s com um
  // arquivo de 18 torneios) deixa de alcancar o jogador. A partir do recibo, o arquivo esta
  // guardado: fechar a aba nao perde nada, e reenviar o mesmo arquivo devolve o MESMO recibo.
  useEffect(() => {
    const next = queue.find((i) => i.status === "queued");
    if (!next || processing.current) return;

    processing.current = true;
    dispatch({ type: "SET_STATUS", id: next.id, status: "processing" });

    const file = fileMap.current.get(next.id);

    (async () => {
      try {
        if (!file) throw new Error(t("uploadQueue.fileMissing"));
        const content = await file.text();
        const r = await tournaments.receber(content, file.name);
        if (r?.kind === "summary") {
          // Era um Tournament Summary, não hand history: dados do torneio complementados.
          const note = r.field_size != null
            ? t("uploadQueue.summaryWithField", { n: r.field_size })
            : t("uploadQueue.summaryPlain");
          dispatch({ type: "SET_STATUS", id: next.id, status: "done", note });
          window.dispatchEvent(new CustomEvent("leaklab:tournament-imported"));
        } else if (r?.recibo) {
          // GUARDADO. Dali em diante quem manda no desfecho e a fase 2, lendo o recibo.
          dispatch({ type: "SET_RECIBO", id: next.id, recibo: r.recibo,
                     note: t("uploadQueue.recebido") });
        } else {
          throw new Error(t("uploadQueue.fileMissing"));
        }
      } catch (e: unknown) {
        // A frase honesta (limite por hora + minutos) ou a msg do backend; nunca "HTTP 404" cru.
        dispatch({ type: "SET_STATUS", id: next.id, status: "error", error: mensagemDeErroDeUpload(e, t) });
      } finally {
        processing.current = false;
      }
    })();
    // `t` fica FORA das dependências de propósito: ele só compõe mensagens de erro dentro do
    // callback, e sua identidade muda ao trocar de idioma — incluí-lo re-dispararia o loop de
    // upload no meio de um envio. O idioma da mensagem é o do momento em que ela é gerada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue]);

  // ── FASE 2: ACOMPANHAR ────────────────────────────────────────────────────────────────
  // Pergunta o andamento de cada recibo enquanto houver algum em curso. Um unico temporizador
  // para a lista inteira, e nao um por arquivo: N temporizadores em paralelo multiplicariam as
  // consultas justamente quando o servidor esta ocupado processando.
  useEffect(() => {
    const emCurso = queue.filter((i) => i.status === "processing" && i.recibo);
    if (emCurso.length === 0) return;

    let vivo = true;
    const timer = setInterval(async () => {
      for (const item of emCurso) {
        if (!vivo) return;
        let r;
        try {
          r = await tournaments.recibo(item.recibo!);
        } catch {
          // Falha de rede AQUI nao e falha do upload: o arquivo esta guardado. Fica em curso e
          // a proxima volta tenta de novo. Marcar erro aqui seria repetir o defeito que esta
          // frente existe para consertar -- dizer que falhou o que deu certo.
          continue;
        }
        if (!vivo) return;

        if (r.status === "erro") {
          dispatch({ type: "SET_STATUS", id: item.id, status: "error",
                     error: r.erro || t("uploadQueue.erroNoProcessamento") });
          continue;
        }
        if (r.status !== "concluido") {
          // Em curso: mostra o progresso real quando o worker ja dividiu o arquivo.
          const nota = r.torneios_no_arquivo
            ? t("uploadQueue.progresso", { feitos: r.torneios_gravados + r.torneios_ja_estavam,
                                           total: r.torneios_no_arquivo })
            : t("uploadQueue.recebido");
          if (nota !== item.note) {
            dispatch({ type: "SET_RECIBO", id: item.id, recibo: item.recibo!, note: nota });
          }
          continue;
        }

        // Concluido. A frase e a MESMA de sempre (`notaDaContagem`), com a copy que ja esta
        // nas tres locales: "ja estava no historico" nao e perda de dado, e omitir isso fazia
        // o jogador procurar torneio que nao falta.
        //
        // A nota da fila de analise se SOMA a do arquivo em vez de substitui-la: um jogador
        // Free que sobe 36 torneios precisa saber as duas coisas. Na primeira versao desta
        // frente ela desapareceu calada, e foi o teste de fiacao que pegou.
        const varios = notaDaContagem(contagemDoRecibo(r), t);
        const naFila = (r.detalhe ?? []).some((d) => d.analysis_waitlisted);
        const note = naFila
          ? [varios, t("uploadQueue.analiseNaFila")].filter(Boolean).join(" ")
          : varios;
        dispatch({ type: "SET_STATUS", id: item.id, status: "done", note });

        // XP por TORNEIO que entrou, nao por arquivo (decisao do dono, 13/09): quem sobe 36
        // torneios num export do PartyPoker ganharia o mesmo de quem sobe um. Conta so os
        // NOVOS -- torneio que ja estava no historico nao e jogo novo. O valor de cada um fica
        // no backend, aqui vai a quantidade.
        if (r.torneios_gravados > 0) {
          metrics.addXp("tournament_imported", undefined, r.torneios_gravados).catch(() => null);
          window.dispatchEvent(new CustomEvent("leaklab:tournament-imported"));
        }
      }
    }, 2500);

    return () => { vivo = false; clearInterval(timer); };
    // `t` fora das dependencias pela mesma razao da fase 1: trocar de idioma no meio do
    // acompanhamento nao pode reiniciar o temporizador.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue]);

  // Refresh pós-import é global: o loop dispara `leaklab:tournament-imported` a cada conclusão,
  // e as telas interessadas (Index, Tournaments) escutam e recarregam. Sem callback por consumidor.
  const panel = queue.length > 0 ? (
    <QueuePanel items={queue} onDismiss={dismiss} onClearDone={clearDone} />
  ) : null;

  return (
    <UploadQueueContext.Provider value={{ enqueue }}>
      {children}
      {panel}
    </UploadQueueContext.Provider>
  );
}
