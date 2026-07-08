import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Users, Dumbbell } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  LessonSection, Prose, Callout, TableScene, CardRow, Takeaways, NextStep,
} from "@/components/academy/LessonKit";
import { QuizRunner } from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";
import type { ReplayStep, ReplaySeat } from "@/lib/api";

// Monta um ReplayStep didático mínimo para a mesa ATUAL (PokerTableV3).
function scene(over: Partial<ReplayStep> & { seats: Record<string, ReplaySeat> }): ReplayStep {
  return {
    type: "street", desc: "", street: "flop",
    hero: "", hero_cards: [], board: [], pot: 0, pot_bb: 0,
    bets: {}, folded: [], bb: 1, button: 1,
    ...over,
  };
}

export default function AcademyMultiway() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.multiway.${k}`);
  const you = L("seat_you"), vA = L("seat_vA"), vB = L("seat_vB");

  const loadDrill   = useCallback(() => academy.multiwayQuestion(), []);
  const submitDrill = useCallback(
    (idx: number, ci: number, xp: number) => { academy.multiwaySubmit(idx, ci, xp).catch(() => {}); },
    [],
  );

  // Cena 1 — pote 3-way no flop. Herói (BTN) com projeto de nut flush.
  const flopStep = scene({
    type: "street", street: "flop",
    seats: {
      "1": { player: vA, stack: 41, stack_bb: 41, pos: "CO" },
      "2": { player: you, stack: 38, stack_bb: 38, pos: "BTN" },
      "3": { player: vB, stack: 55, stack_bb: 55, pos: "BB" },
    },
    hero: you, hero_cards: ["Ah", "Kh"], board: ["Qh", "7c", "2h"],
    pot: 9, pot_bb: 9, button: 2,
  });

  // Cena 2 — "macaco no meio": A apostou, você age no meio, B ainda vai agir.
  const middleStep = scene({
    type: "action", street: "flop", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: vA, stack: 38, stack_bb: 38, pos: "UTG" },
      "2": { player: you, stack: 40, stack_bb: 40, pos: "HJ" },
      "3": { player: vB, stack: 46, stack_bb: 46, pos: "CO" },
    },
    hero: you, hero_cards: ["As", "Jd"], board: ["Qh", "7c", "2h"],
    bets: { [vA]: 3 }, pot: 6, pot_bb: 6, button: 3,
  });

  return (
    <HudLayout eyebrow={L("eyebrow")} title={L("title")} description={L("subtitle")}>
      <article className="mx-auto max-w-2xl space-y-12 pb-8">

        <LessonSection n={1} title={L("s1_title")}>
          <Prose html={L("s1_p1")} />
          <TableScene step={flopStep} hero={you} heroCards={["Ah", "Kh"]} caption={L("scene1_cap")} />
        </LessonSection>

        <LessonSection n={2} title={L("s2_title")}>
          <Prose html={L("s2_p1")} />
          <Callout tone="warn" title={L("s2_callout_title")}>{L("s2_callout")}</Callout>
        </LessonSection>

        <LessonSection n={3} title={L("s3_title")}>
          <Prose html={L("s3_p1")} />
          <CardRow
            groups={[
              { cards: ["Ah", "Kh"], label: L("cards_good"), tone: "good" },
              { cards: ["8c", "8d"], label: L("cards_bad"), tone: "bad" },
            ]}
            caption={L("cards_cap")}
          />
        </LessonSection>

        <LessonSection n={4} title={L("s4_title")}>
          <Prose html={L("s4_p1")} />
          <Callout tone="tip" title={L("s4_callout_title")}>{L("s4_callout")}</Callout>
        </LessonSection>

        <LessonSection n={5} title={L("s5_title")}>
          <Prose html={L("s5_p1")} />
          <TableScene step={middleStep} hero={you} heroCards={["As", "Jd"]} caption={L("scene5_cap")} />
        </LessonSection>

        <LessonSection n={6} title={L("s6_title")}>
          <Prose html={L("s6_p1")} />
        </LessonSection>

        <Takeaways title={L("takeaways_title")} items={[L("t1"), L("t2"), L("t3"), L("t4")]} />

        {/* Treino específico da aula — dentro do próprio material */}
        <section className="space-y-4 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-rose-300">
              <Dumbbell className="size-3.5" aria-hidden />
              {L("drill_title")}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{L("drill_sub")}</p>
          </div>
          <QuizRunner theme="violet" Icon={Users} loadFn={loadDrill} submitFn={submitDrill} />
        </section>

        <NextStep to="/training" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
