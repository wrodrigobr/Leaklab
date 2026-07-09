import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Coins, Dumbbell } from "lucide-react";
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

export default function AcademyPko() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.pko.${k}`);
  const you = L("seat_you"), covered = L("seat_covered"), big = L("seat_big");

  const loadDrill   = useCallback(() => academy.pkoQuestion(), []);
  const submitDrill = useCallback(
    (idx: number, ci: number, xp: number) => { academy.pkoSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );

  // Cena 1 — você COBRE o short que shovou: capturar o bounty amplia o call.
  const coverStep = scene({
    type: "action", street: "preflop", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: covered, stack: 9, stack_bb: 9, pos: "SB" },
      "2": { player: you, stack: 40, stack_bb: 40, pos: "BB" },
      "3": { player: big, stack: 55, stack_bb: 55, pos: "BTN" },
    },
    hero: you, hero_cards: ["Ad", "Ts"], board: [],
    bets: { [covered]: 9 }, pot: 10.5, pot_bb: 10.5, button: 3,
  });

  // Cena 2 — você é o short: NÃO cobre ninguém, o bounty não te ajuda.
  const shortStep = scene({
    type: "action", street: "preflop", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: big, stack: 48, stack_bb: 48, pos: "BB" },
      "2": { player: you, stack: 7, stack_bb: 7, pos: "BTN" },
      "3": { player: covered, stack: 30, stack_bb: 30, pos: "CO" },
    },
    hero: you, hero_cards: ["Kh", "Qh"], board: [],
    pot: 1.5, pot_bb: 1.5, button: 2,
  });

  return (
    <HudLayout eyebrow={L("eyebrow")} title={L("title")} description={L("subtitle")}>
      <article className="max-w-4xl space-y-12 pb-8">

        <LessonSection n={1} title={L("intro_title")}>
          <Prose html={L("intro_p1")} />
          <Prose html={L("intro_p2")} />
          <Callout tone="note" title={L("intro_note_title")}>{L("intro_note")}</Callout>
        </LessonSection>

        <Objectives title={L("obj_title")} items={[L("obj1"), L("obj2"), L("obj3"), L("obj4")]} />

        <LessonSection n={2} title={L("fund_title")}>
          <Prose html={L("fund_p1")} />
          <Prose html={L("fund_p2")} />
          <LessonTable
            headers={[L("tbl_h1"), L("tbl_h2"), L("tbl_h3")]}
            rows={[
              [L("tbl_r1_a"), L("tbl_r1_b"), L("tbl_r1_c")],
              [L("tbl_r2_a"), L("tbl_r2_b"), L("tbl_r2_c")],
              [L("tbl_r3_a"), L("tbl_r3_b"), L("tbl_r3_c")],
            ]}
          />
        </LessonSection>

        <LessonSection n={3} title={L("c1_title")}>
          <Prose html={L("c1_p1")} />
          <TableScene step={coverStep} hero={you} heroCards={["Ad", "Ts"]} caption={L("c1_cap")} />
          <Callout tone="key" title={L("c1_key_title")}>{L("c1_key")}</Callout>
        </LessonSection>

        <LessonSection n={4} title={L("c2_title")}>
          <Prose html={L("c2_p1")} />
          <TableScene step={shortStep} hero={you} heroCards={["Kh", "Qh"]} caption={L("c2_cap")} />
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

        <section className="space-y-4 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-rose-300">
              <Dumbbell className="size-3.5" aria-hidden />
              {L("drill_title")}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{L("drill_sub")}</p>
          </div>
          <QuizRunner theme="violet" Icon={Coins} loadFn={loadDrill} submitFn={submitDrill} />
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

        <NextStep to="/academy/icm" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
