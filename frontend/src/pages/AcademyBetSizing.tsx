import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { BookOpen, Dumbbell } from "lucide-react";
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
    type: "street", desc: "", street: "flop",
    hero: "", hero_cards: [], board: [], pot: 0, pot_bb: 0,
    bets: {}, folded: [], bb: 1, button: 1,
    ...over,
  };
}

export default function AcademyBetSizing() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.bet_sizing.${k}`);
  const you = L("seat_you"), vil = L("seat_vil");

  const loadDrill   = useCallback(() => academy.sizingQuestion(), []);
  const submitDrill = useCallback(
    (idx: number, ci: number, xp: number) => { academy.sizingSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );

  // Cena — SPR baixo (~2): pote 20, stacks 40, top par num board seco.
  const sprStep = scene({
    type: "action", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: vil, stack: 40, stack_bb: 40, pos: "BB" },
      "2": { player: you, stack: 40, stack_bb: 40, pos: "BTN" },
    },
    hero: you, hero_cards: ["Kh", "Qd"], board: ["Kd", "8s", "3c"],
    pot: 20, pot_bb: 20, button: 2,
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
        </LessonSection>

        <LessonSection n={3} title={L("c1_title")}>
          <Prose html={L("c1_p1")} />
          <Callout tone="key" title={L("c1_key_title")}>{L("c1_key")}</Callout>
        </LessonSection>

        <LessonSection n={4} title={L("c2_title")}>
          <Prose html={L("c2_p1")} />
          <Callout tone="tip" title={L("c2_tip_title")}>{L("c2_tip")}</Callout>
        </LessonSection>

        <LessonSection n={5} title={L("c3_title")}>
          <Prose html={L("c3_p1")} />
          <LessonTable
            headers={[L("cheat_h1"), L("cheat_h2")]}
            rows={[
              [L("cheat_r1_a"), L("cheat_r1_b")],
              [L("cheat_r2_a"), L("cheat_r2_b")],
              [L("cheat_r3_a"), L("cheat_r3_b")],
              [L("cheat_r4_a"), L("cheat_r4_b")],
              [L("cheat_r5_a"), L("cheat_r5_b")],
            ]}
          />
        </LessonSection>

        <LessonSection n={6} title={L("c4_title")}>
          <Prose html={L("c4_p1")} />
          <TableScene step={sprStep} hero={you} heroCards={["Kh", "Qd"]} caption={L("c4_cap")} />
          <Callout tone="coach" title={L("c4_coach_title")}>{L("c4_coach")}</Callout>
        </LessonSection>

        <LessonSection n={7} title={L("c5_title")}>
          <Prose html={L("c5_p1")} />
          <Callout tone="curio" title={L("c5_curio_title")}>{L("c5_curio")}</Callout>
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

        <section className="space-y-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-amber-300">
              <Dumbbell className="size-3.5" aria-hidden />
              {L("drill_title")}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{L("drill_sub")}</p>
          </div>
          <QuizRunner theme="amber" Icon={BookOpen} loadFn={loadDrill} submitFn={submitDrill} />
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

        <NextStep to="/academy/postflop" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
