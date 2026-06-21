import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Copy, Check, Link2, CheckCircle2, Clock } from "lucide-react";
import { coachDashboard, StudentSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

// Standing de pagamento → badge (régua da comissão é is_active_paid, standing é o detalhe).
const STANDING_META: Record<
  NonNullable<StudentSummary["billing_standing"]>,
  { key: string; cls: string }
> = {
  paying:   { key: "standingPaying",  cls: "bg-primary/10 text-primary ring-1 ring-primary/20" },
  past_due: { key: "standingPastDue", cls: "bg-amber-400/10 text-amber-400 ring-1 ring-amber-400/30" },
  perk:     { key: "standingPerk",    cls: "bg-border text-muted-foreground ring-1 ring-border" },
  free:     { key: "standingFree",    cls: "bg-border text-muted-foreground ring-1 ring-border" },
};

// ── Feature 1: tabela de alunos indicados ──────────────────────────────────────
export function ReferredStudentsCard() {
  const { t } = useTranslation("dashboard");
  const { data } = useQuery({ queryKey: ["coach-students"], queryFn: coachDashboard.students });
  const referred = (data?.students ?? []).filter((s) => s.is_referred === true);
  const payingCount = referred.filter((s) => s.is_active_paid === true).length;

  return (
    <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
      <div className="px-4 py-3 border-b border-border bg-hud-elevated/40 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("coachReferral.referredTitle")}
          </span>
          <span className="font-mono text-[10px] text-primary tabular-nums">
            {t("coachReferral.summary", { paying: payingCount, total: referred.length })}
          </span>
        </div>
        <p className="font-mono text-[9px] text-muted-foreground/70">{t("coachReferral.referredHint")}</p>
      </div>

      {referred.length === 0 ? (
        <p className="px-4 py-8 text-sm text-muted-foreground text-center">{t("coachReferral.empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                {[
                  t("coachReferral.colStudent"),
                  t("coachReferral.colPlan"),
                  t("coachReferral.colStanding"),
                  t("coachReferral.colLink"),
                  t("coachReferral.colCommission"),
                ].map((h, i) => (
                  <th
                    key={i}
                    className={cn(
                      "px-4 py-2.5 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground",
                      i === 0 ? "text-left" : "text-center"
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {referred.map((s) => {
                const standing = STANDING_META[s.billing_standing ?? "free"];
                const isPro = s.plan === "pro";
                const counts = s.is_active_paid === true;
                return (
                  <tr key={s.id} className="hover:bg-primary/5 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 font-bold text-primary text-xs uppercase">
                          {s.username[0]}
                        </div>
                        <span className="font-medium text-foreground">{s.username}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-sm px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider",
                          isPro
                            ? "bg-primary/10 text-primary ring-1 ring-primary/20"
                            : "bg-border text-muted-foreground ring-1 ring-border"
                        )}
                      >
                        {isPro ? t("coachReferral.planPro") : t("coachReferral.planFree")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-sm px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider",
                          standing.cls
                        )}
                      >
                        {t(`coachReferral.${standing.key}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {s.link_status === "approved" ? (
                        <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary">
                          <CheckCircle2 className="size-3" /> {t("coachReferral.linkApproved")}
                        </span>
                      ) : s.link_status === "rejected" ? (
                        <span className="inline-flex items-center font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                          {t("coachReferral.linkRejected")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-300">
                          <Clock className="size-3" /> {t("coachReferral.linkPending")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {counts ? (
                        <span
                          title={t("coachReferral.countsTitle")}
                          className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20"
                        >
                          <CheckCircle2 className="size-3" /> {t("coachReferral.counts")}
                        </span>
                      ) : (
                        <span
                          title={t("coachReferral.notCountsTitle")}
                          className="inline-flex items-center rounded-sm bg-border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground ring-1 ring-border"
                        >
                          {t("coachReferral.notCounts")}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Feature 2: card do link de indicação ───────────────────────────────────────
export function ReferralLinkCard() {
  const { t } = useTranslation("dashboard");
  const [copied, setCopied] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["coach-invite-key"], queryFn: coachDashboard.inviteKey });

  const link = useMemo(() => {
    if (!data?.invite_key) return null;
    // /login é a rota de cadastro (aba "register"); o ?ref vincula ao coach na inscrição.
    return `${window.location.origin}/login?ref=${encodeURIComponent(data.invite_key)}`;
  }, [data?.invite_key]);

  const copy = () => {
    if (!link) return;
    navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center gap-1.5">
        <Link2 className="size-3.5 text-primary" />
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {t("coachReferral.linkTitle")}
        </p>
      </div>

      {isLoading || !link ? (
        <p className="font-mono text-[10px] text-muted-foreground py-2">{t("coachReferral.loading")}</p>
      ) : (
        <>
          <div className="flex items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5">
            <code className="flex-1 min-w-0 truncate font-mono text-xs text-foreground">{link}</code>
            <button
              onClick={copy}
              title={t("coachReferral.copy")}
              className="shrink-0 text-muted-foreground hover:text-primary transition-colors"
            >
              {copied ? <Check className="size-3.5 text-primary" /> : <Copy className="size-3.5" />}
            </button>
          </div>
          <button
            onClick={copy}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-primary/10 px-2.5 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 transition-colors"
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
            {copied ? t("coachReferral.copied") : t("coachReferral.copy")}
          </button>
        </>
      )}

      <p className="text-xs text-muted-foreground leading-relaxed">{t("coachReferral.linkExplain")}</p>
    </div>
  );
}
