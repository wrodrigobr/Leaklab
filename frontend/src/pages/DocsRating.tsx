import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";

/**
 * /docs/rating — explica a teoria ELO e como adaptamos pro LeakLab.
 * Conteúdo via i18n (namespace `docs`, bloco `rating.*`). Prosa com markup usa
 * dangerouslySetInnerHTML (mesmo padrão de Docs.tsx). Ícones/ranges são neutros
 * de idioma e ficam no componente; só nomes de banda e textos vêm do i18n.
 */
export default function DocsRating() {
  const { t } = useTranslation("docs");

  // Tabela de qualidade da decisão (cor por linha; texto via i18n)
  const QUALITY: { key: string; color: string }[] = [
    { key: "q_correct", color: "text-emerald-400" },
    { key: "q_mixed",   color: "text-sky-400" },
    { key: "q_minor",   color: "text-amber-400" },
    { key: "q_major",   color: "text-red-400" },
  ];

  // Bandas: ícone (emoji) + range são neutros de idioma; nome/perfil via i18n
  const BANDS: { key: string; icon: string; range: string }[] = [
    { key: "b_beginner", icon: "🎯", range: "< 1570" },
    { key: "b_student",  icon: "📖", range: "1570 – 1646" },
    { key: "b_grinder",  icon: "⚙️", range: "1647 – 1709" },
    { key: "b_regular",  icon: "📈", range: "1710 – 1815" },
    { key: "b_solid",    icon: "🔷", range: "1816 – 1923" },
    { key: "b_expert",   icon: "♠",  range: "1924 – 2052" },
    { key: "b_elite",    icon: "👑", range: "≥ 2053" },
  ];

  const BackLink = () => (
    <Link to="/rating" className="inline-flex items-center gap-1.5 font-mono text-xs text-primary hover:underline">
      <ArrowLeft className="size-3.5" /> {t("rating.back")}
    </Link>
  );

  const H2 = ({ k }: { k: string }) => (
    <h2 className="text-lg font-semibold text-foreground border-b border-border pb-2">{t(k)}</h2>
  );

  const P = ({ k, className }: { k: string; className?: string }) => (
    <p className={className} dangerouslySetInnerHTML={{ __html: t(k) }} />
  );

  return (
    <HudLayout
      eyebrow={t("rating.eyebrow")}
      title={t("rating.title")}
      description={t("rating.description")}
    >
      <div className="max-w-3xl space-y-8 text-sm text-muted-foreground leading-relaxed">

        <BackLink />

        <section className="space-y-3">
          <H2 k="rating.s1_title" />
          <P k="rating.s1_p1" />
          <P k="rating.s1_p2" />
        </section>

        <section className="space-y-3">
          <H2 k="rating.s2_title" />
          <P k="rating.s2_p1" />
          <P k="rating.s2_p2" />
        </section>

        <section className="space-y-3">
          <H2 k="rating.s3_title" />
          <P k="rating.s3_p1" />
          <P k="rating.s3_note" className="rounded-md bg-emerald-500/10 border border-emerald-500/30 p-3 text-emerald-300/90 text-xs" />
          <P k="rating.s3_p2" />
          <div className="rounded-lg border border-border/40 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-card/60">
                <tr>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">{t("rating.q_col_class")}</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">{t("rating.q_col_meaning")}</th>
                </tr>
              </thead>
              <tbody>
                {QUALITY.map((q) => (
                  <tr key={q.key} className="border-t border-border/30">
                    <td className={`px-3 py-2 ${q.color}`}>{t(`rating.${q.key}`)}</td>
                    <td className="px-3 py-2">{t(`rating.${q.key}_desc`)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <H2 k="rating.s4_title" />
          <P k="rating.s4_p1" />
        </section>

        <section className="space-y-3">
          <H2 k="rating.s5_title" />
          <div className="rounded-lg border border-border/40 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-card/60">
                <tr>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">{t("rating.b_col_band")}</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">{t("rating.b_col_range")}</th>
                  <th className="px-3 py-2 text-left font-mono uppercase tracking-wider">{t("rating.b_col_profile")}</th>
                </tr>
              </thead>
              <tbody>
                {BANDS.map((b) => (
                  <tr key={b.key} className="border-t border-border/30">
                    <td className="px-3 py-2 font-mono">{b.icon} {t(`rating.${b.key}`)}</td>
                    <td className="px-3 py-2 font-mono">{b.range}</td>
                    <td className="px-3 py-2">{t(`rating.${b.key}_profile`)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <H2 k="rating.s6_title" />
          <ul className="list-disc list-inside space-y-2">
            <li dangerouslySetInnerHTML={{ __html: t("rating.n1") }} />
            <li dangerouslySetInnerHTML={{ __html: t("rating.n2") }} />
            <li dangerouslySetInnerHTML={{ __html: t("rating.n3") }} />
            <li dangerouslySetInnerHTML={{ __html: t("rating.n4") }} />
          </ul>
        </section>

        <BackLink />
      </div>
    </HudLayout>
  );
}
