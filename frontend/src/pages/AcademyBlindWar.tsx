import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Sword, Dumbbell } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  LessonSection, Prose, Callout, TableScene, LessonTable, Objectives, PlayerCompare,
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

export default function AcademyBlindWar() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.bvb.${k}`);
  const you = L("seat_you"), vil = L("seat_vil");

  const loadDrill   = useCallback(() => academy.bvbQuestion(), []);
  const submitDrill = useCallback(
    (idx: number, ci: number, xp: number) => { academy.bvbSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );

  // Cena 1 — SB ataca: folded to você no SB, Q8s, você abre (range larga).
  const sbStep = scene({
    type: "action", seat: 1, player: you, is_hero: true,
    seats: {
      "1": { player: you, stack: 40, stack_bb: 40, pos: "SB" },
      "2": { player: vil, stack: 40, stack_bb: 40, pos: "BB" },
    },
    hero: you, hero_cards: ["Qh", "8h"], board: [],
    bets: { [you]: 2.5 }, pot: 3.5, pot_bb: 3.5, button: 1,
  });

  // Cena 2 — BB defende: o SB abriu 2,5bb, você no BB com K9o paga (defende largo, em posição).
  const bbStep = scene({
    type: "action", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: vil, stack: 40, stack_bb: 40, pos: "SB" },
      "2": { player: you, stack: 40, stack_bb: 40, pos: "BB" },
    },
    hero: you, hero_cards: ["Kd", "9c"], board: [],
    bets: { [vil]: 2.5 }, pot: 3.5, pot_bb: 3.5, button: 1,
  });

  return (
    <HudLayout eyebrow={L("eyebrow")} title={L("title")} description={L("subtitle")}>
      <article className="mx-auto max-w-6xl space-y-12 pb-8">

        <LessonSection n={1} title={L("intro_title")}>
          <Prose html={L("intro_p1")} />
          <Prose html={L("intro_p2")} />
          <Callout tone="note" title={L("intro_note_title")}>{L("intro_note")}</Callout>
        </LessonSection>

        <Objectives title={L("obj_title")} items={[L("obj1"), L("obj2"), L("obj3"), L("obj4")]} />

        <LessonSection n={2} title={L("fund_title")}>
          <Prose html={L("fund_p1")} />
          <Prose html={L("fund_p2")} />
          <Callout tone="key" title={L("fund_key_title")}>{L("fund_key")}</Callout>
        </LessonSection>

        <LessonSection n={3} title={L("c1_title")}>
          <Prose html={L("c1_p1")} />
          <TableScene step={sbStep} hero={you} heroCards={["Qh", "8h"]} caption={L("c1_cap")} />
          <Callout tone="tip" title={L("c1_tip_title")}>{L("c1_tip")}</Callout>
        </LessonSection>

        <LessonSection n={4} title={L("c2_title")}>
          <Prose html={L("c2_p1")} />
          <TableScene step={bbStep} hero={you} heroCards={["Kd", "9c"]} caption={L("c2_cap")} />
          <Callout tone="key" title={L("c2_key_title")}>{L("c2_key")}</Callout>
        </LessonSection>

        <LessonSection n={5} title={L("c3_title")}>
          <Prose html={L("c3_p1")} />
          <LessonTable
            headers={[L("tbl_h1"), L("tbl_h2"), L("tbl_h3")]}
            rows={[
              [L("tbl_r1_a"), L("tbl_r1_b"), L("tbl_r1_c")],
              [L("tbl_r2_a"), L("tbl_r2_b"), L("tbl_r2_c")],
            ]}
          />
          <Callout tone="warn" title={L("c3_warn_title")}>{L("c3_warn")}</Callout>
        </LessonSection>

        <LessonSection n={6} title={L("c4_title")}>
          <Prose html={L("c4_p1")} />
          <Callout tone="coach" title={L("c4_coach_title")}>{L("c4_coach")}</Callout>
        </LessonSection>

        <LessonSection n={7} title={L("ex_title")}>
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
          ]}
        />

        <Checklist title={L("chk_title")} items={[L("chk1"), L("chk2"), L("chk3"), L("chk4"), L("chk5")]} />

        <section className="space-y-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-amber-300">
              <Dumbbell className="size-3.5" aria-hidden />
              {L("drill_title")}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{L("drill_sub")}</p>
          </div>
          <QuizRunner theme="amber" Icon={Sword} loadFn={loadDrill} submitFn={submitDrill} />
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
          ]}
        />

        <GrindLabDetects
          title={L("gl_title")}
          intro={L("gl_intro")}
          items={[L("gl1"), L("gl2"), L("gl3"), L("gl4")]}
        />

        <NextStep to="/academy/position" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
