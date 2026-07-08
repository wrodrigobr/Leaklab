import { useTranslation } from "react-i18next";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  LessonSection, Prose, Callout, TableScene, CardRow, Takeaways, LessonQuiz, NextStep,
  type QuizItem,
} from "@/components/academy/LessonKit";
import type { CardData } from "@/components/hud/PlayingCard";
import type { Seat } from "@/components/hud/PokerTable";

// Cartas didáticas (nossos componentes, dados fixos)
const C = (rank: string, suit: CardData["suit"]): CardData => ({ rank, suit });

export default function AcademyMultiway() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.multiway.${k}`);

  // Cena 1 — pote 3-way no flop. Herói com projeto de nut flush.
  const flopSeats: Seat[] = [
    { id: 1, name: L("seat_vA"), stack: 41 },
    { id: 2, name: L("seat_you"), stack: 38, hero: true, cards: [C("A", "h"), C("K", "h")] },
    { id: 3, name: L("seat_vB"), stack: 55 },
  ];
  const flopBoard: CardData[] = [C("Q", "h"), C("7", "c"), C("2", "h")];

  // Cena 2 — "macaco no meio": A apostou, você age no meio, B ainda vai agir.
  const middleSeats: Seat[] = [
    { id: 1, name: L("seat_vA"), stack: 38, bet: 3 },
    { id: 2, name: L("seat_you"), stack: 40, hero: true, active: true, cards: [C("A", "s"), C("J", "d")] },
    { id: 3, name: L("seat_vB"), stack: 46 },
  ];

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
          <TableScene seats={flopSeats} community={flopBoard} pot={9} street={L("street_flop")} caption={L("scene1_cap")} />
        </LessonSection>

        <LessonSection n={2} title={L("s2_title")}>
          <Prose html={L("s2_p1")} />
          <Callout tone="warn" title={L("s2_callout_title")}>{L("s2_callout")}</Callout>
        </LessonSection>

        <LessonSection n={3} title={L("s3_title")}>
          <Prose html={L("s3_p1")} />
          <CardRow
            groups={[
              { cards: [C("A", "h"), C("K", "h")], label: L("cards_good"), tone: "good" },
              { cards: [C("8", "c"), C("8", "d")], label: L("cards_bad"), tone: "bad" },
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
          <TableScene seats={middleSeats} pot={6} street={L("street_flop")} caption={L("scene5_cap")} />
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
