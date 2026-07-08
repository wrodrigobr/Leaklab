import { useTranslation } from "react-i18next";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  LessonSection, Prose, Callout, TableScene, CardRow, Takeaways, LessonQuiz, NextStep,
  type QuizItem,
} from "@/components/academy/LessonKit";
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

  const quiz: QuizItem[] = [
    { q: L("q1"), options: [L("q1a"), L("q1b"), L("q1c")], correct: 2, explain: L("q1e") },
    { q: L("q2"), options: [L("q2a"), L("q2b"), L("q2c")], correct: 2, explain: L("q2e") },
    { q: L("q3"), options: [L("q3a"), L("q3b"), L("q3c")], correct: 1, explain: L("q3e") },
  ];

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

        <LessonQuiz title={L("quiz_title")} items={quiz} />

        <NextStep to="/training" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
