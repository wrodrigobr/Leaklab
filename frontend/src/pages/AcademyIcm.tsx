import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Brain, Dumbbell } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  LessonSection, Prose, Callout, TableScene, Objectives, PlayerCompare,
  Mistakes, Checklist, Glossary, GrindLabDetects, Takeaways, NextStep,
} from "@/components/academy/LessonKit";
import { QuizRunner } from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";
import type { ReplayStep, ReplaySeat } from "@/lib/api";

function scene(over: Partial<ReplayStep> & { seats: Record<string, ReplaySeat> }): ReplayStep {
  return {
    type: "street", desc: "", street: "preflop",
    hero: "", hero_cards: [], board: [], pot: 0, pot_bb: 0,
    bets: {}, folded: [], bb: 1, button: 1,
    ...over,
  };
}

export default function AcademyIcm() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.icm.${k}`);
  const you = L("seat_you"), lead = L("seat_lead"), short = L("seat_short");

  const loadDrill   = useCallback(() => academy.icmQuestion(), []);
  const submitDrill = useCallback(
    (idx: number, ci: number, xp: number) => { academy.icmSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );

  // Cena 1 — bolha: o chip leader shova, você (stack médio) tem mão marginal, um short atrás.
  const bubbleStep = scene({
    type: "action", street: "preflop", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: lead, stack: 62, stack_bb: 62, pos: "BTN" },
      "2": { player: you, stack: 15, stack_bb: 15, pos: "BB" },
      "3": { player: short, stack: 5, stack_bb: 5, pos: "SB" },
    },
    hero: you, hero_cards: ["Ah", "Jc"], board: [],
    bets: { [lead]: 15 }, pot: 8, pot_bb: 8, button: 1,
  });

  // Cena 2 — você é o big stack pressionando um short perto do dinheiro.
  const pressStep = scene({
    type: "action", street: "preflop", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: short, stack: 5, stack_bb: 5, pos: "BB" },
      "2": { player: you, stack: 60, stack_bb: 60, pos: "BTN" },
      "3": { player: lead, stack: 24, stack_bb: 24, pos: "CO" },
    },
    hero: you, hero_cards: ["Kd", "Ts"], board: [],
    pot: 1.5, pot_bb: 1.5, button: 2,
  });

  return (
    <HudLayout eyebrow={L("eyebrow")} title={L("title")} description={L("subtitle")}>
      <article className="mx-auto max-w-2xl space-y-12 pb-8">

        <LessonSection n={1} title={L("intro_title")}>
          <Prose html={L("intro_p1")} />
          <Prose html={L("intro_p2")} />
          <Callout tone="note" title={L("intro_note_title")}>{L("intro_note")}</Callout>
        </LessonSection>

        <Objectives title={L("obj_title")} items={[L("obj1"), L("obj2"), L("obj3"), L("obj4")]} />

        <LessonSection n={2} title={L("fund_title")}>
          <Prose html={L("fund_p1")} />
          <Prose html={L("fund_p2")} />
        </LessonSection>

        <LessonSection n={3} title={L("c1_title")}>
          <Prose html={L("c1_p1")} />
          <Prose html={L("c1_p2")} />
          <Callout tone="key" title={L("c1_key_title")}>{L("c1_key")}</Callout>
        </LessonSection>

        <LessonSection n={4} title={L("c2_title")}>
          <Prose html={L("c2_p1")} />
          <TableScene step={bubbleStep} hero={you} heroCards={["Ah", "Jc"]} caption={L("c2_cap")} />
          <Prose html={L("c2_p2")} />
          <Callout tone="warn" title={L("c2_warn_title")}>{L("c2_warn")}</Callout>
        </LessonSection>

        <LessonSection n={5} title={L("c3_title")}>
          <Prose html={L("c3_p1")} />
          <Callout tone="tip" title={L("c3_tip_title")}>{L("c3_tip")}</Callout>
        </LessonSection>

        <LessonSection n={6} title={L("c4_title")}>
          <Prose html={L("c4_p1")} />
          <Callout tone="coach" title={L("c4_coach_title")}>{L("c4_coach")}</Callout>
        </LessonSection>

        <LessonSection n={7} title={L("c5_title")}>
          <Prose html={L("c5_p1")} />
          <TableScene step={pressStep} hero={you} heroCards={["Kd", "Ts"]} caption={L("c5_cap")} />
        </LessonSection>

        <LessonSection n={8} title={L("ex_title")}>
          <Prose html={L("ex_p1")} />
          <Prose html={L("ex_p2")} />
        </LessonSection>

        <PlayerCompare
          title={L("cmp_title")}
          cols={[L("cmp_col_rec"), L("cmp_col_reg"), L("cmp_col_pro")]}
          rows={[
            { label: L("cmp_r1"), rec: L("cmp_r1_rec"), reg: L("cmp_r1_reg"), pro: L("cmp_r1_pro") },
            { label: L("cmp_r2"), rec: L("cmp_r2_rec"), reg: L("cmp_r2_reg"), pro: L("cmp_r2_pro") },
            { label: L("cmp_r3"), rec: L("cmp_r3_rec"), reg: L("cmp_r3_reg"), pro: L("cmp_r3_pro") },
          ]}
        />

        <Mistakes
          title={L("err_title")}
          items={[
            { mistake: L("e1_m"), why: L("e1_why"), fix: L("e1_fix") },
            { mistake: L("e2_m"), why: L("e2_why"), fix: L("e2_fix") },
            { mistake: L("e3_m"), why: L("e3_why"), fix: L("e3_fix") },
            { mistake: L("e4_m"), why: L("e4_why"), fix: L("e4_fix") },
            { mistake: L("e5_m"), why: L("e5_why"), fix: L("e5_fix") },
            { mistake: L("e6_m"), why: L("e6_why"), fix: L("e6_fix") },
          ]}
        />

        <Checklist title={L("chk_title")} items={[L("chk1"), L("chk2"), L("chk3"), L("chk4"), L("chk5")]} />

        <section className="space-y-4 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-rose-300">
              <Dumbbell className="size-3.5" aria-hidden />
              {L("drill_title")}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{L("drill_sub")}</p>
          </div>
          <QuizRunner theme="violet" Icon={Brain} loadFn={loadDrill} submitFn={submitDrill} />
        </section>

        <Takeaways title={L("takeaways_title")} items={[L("t1"), L("t2"), L("t3"), L("t4")]} />

        <Glossary
          title={L("glo_title")}
          terms={[
            { term: L("g1_term"), def: L("g1_def") },
            { term: L("g2_term"), def: L("g2_def") },
            { term: L("g3_term"), def: L("g3_def") },
            { term: L("g4_term"), def: L("g4_def") },
            { term: L("g5_term"), def: L("g5_def") },
            { term: L("g6_term"), def: L("g6_def") },
          ]}
        />

        <GrindLabDetects
          title={L("gl_title")}
          intro={L("gl_intro")}
          items={[L("gl1"), L("gl2"), L("gl3"), L("gl4"), L("gl5")]}
        />

        <NextStep to="/academy/multiway" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
