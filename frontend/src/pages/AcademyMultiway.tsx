import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Users, Dumbbell } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  LessonSection, Prose, Callout, TableScene, CardRow, Objectives, PlayerCompare,
  Mistakes, Checklist, Glossary, GrindLabDetects, Takeaways, NextStep,
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
    type: "action", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: vA, stack: 38, stack_bb: 38, pos: "UTG" },
      "2": { player: you, stack: 40, stack_bb: 40, pos: "HJ" },
      "3": { player: vB, stack: 46, stack_bb: 46, pos: "CO" },
    },
    hero: you, hero_cards: ["As", "Jd"], board: ["Qh", "7c", "2h"],
    bets: { [vA]: 3 }, pot: 6, pot_bb: 6, button: 3,
  });

  // Cena 3 — exemplo prático (par médio 3-way enfrentando aposta).
  const exampleStep = scene({
    type: "action", seat: 2, player: you, is_hero: true,
    seats: {
      "1": { player: vA, stack: 44, stack_bb: 44, pos: "MP" },
      "2": { player: you, stack: 40, stack_bb: 40, pos: "CO" },
      "3": { player: vB, stack: 60, stack_bb: 60, pos: "BTN" },
    },
    hero: you, hero_cards: ["9s", "9c"], board: ["Ah", "Td", "6s"],
    bets: { [vA]: 4 }, pot: 10, pot_bb: 10, button: 3,
  });

  return (
    <HudLayout eyebrow={L("eyebrow")} title={L("title")} description={L("subtitle")}>
      <article className="max-w-4xl space-y-12 pb-8">

        {/* 1. Introdução */}
        <LessonSection n={1} title={L("intro_title")}>
          <Prose html={L("intro_p1")} />
          <Prose html={L("intro_p2")} />
          <Callout tone="note" title={L("intro_note_title")}>{L("intro_note")}</Callout>
        </LessonSection>

        {/* 2. Objetivos */}
        <Objectives title={L("obj_title")} items={[L("obj1"), L("obj2"), L("obj3"), L("obj4")]} />

        {/* 3. Conceitos fundamentais */}
        <LessonSection n={2} title={L("fund_title")}>
          <Prose html={L("fund_p1")} />
          <Prose html={L("fund_p2")} />
        </LessonSection>

        {/* Capítulo 1 — o blefe */}
        <LessonSection n={3} title={L("c1_title")}>
          <Prose html={L("c1_p1")} />
          <Prose html={L("c1_p2")} />
          <TableScene step={flopStep} hero={you} heroCards={["Ah", "Kh"]} caption={L("scene1_cap")} />
          <Callout tone="warn" title={L("c1_warn_title")}>{L("c1_warn")}</Callout>
        </LessonSection>

        {/* Capítulo 2 — valor / mãos que seguem */}
        <LessonSection n={4} title={L("c2_title")}>
          <Prose html={L("c2_p1")} />
          <CardRow
            groups={[
              { cards: ["Ah", "Kh"], label: L("cards_good"), tone: "good" },
              { cards: ["8c", "8d"], label: L("cards_bad"), tone: "bad" },
            ]}
            caption={L("cards_cap")}
          />
          <Callout tone="coach" title={L("c2_coach_title")}>{L("c2_coach")}</Callout>
        </LessonSection>

        {/* Capítulo 3 — sizing */}
        <LessonSection n={5} title={L("c3_title")}>
          <Prose html={L("c3_p1")} />
          <Callout tone="tip" title={L("c3_tip_title")}>{L("c3_tip")}</Callout>
        </LessonSection>

        {/* Capítulo 4 — assento do meio */}
        <LessonSection n={6} title={L("c4_title")}>
          <Prose html={L("c4_p1")} />
          <TableScene step={middleStep} hero={you} heroCards={["As", "Jd"]} caption={L("scene5_cap")} />
          <Callout tone="curio" title={L("c4_curio_title")}>{L("c4_curio")}</Callout>
        </LessonSection>

        {/* 5. Exemplo prático completo */}
        <LessonSection n={7} title={L("ex_title")}>
          <Prose html={L("ex_p1")} />
          <TableScene step={exampleStep} hero={you} heroCards={["9s", "9c"]} caption={L("ex_cap")} />
          <Prose html={L("ex_p2")} />
        </LessonSection>

        {/* 6. Como pensa cada jogador */}
        <PlayerCompare
          title={L("cmp_title")}
          cols={[L("cmp_col_rec"), L("cmp_col_reg"), L("cmp_col_pro")]}
          rows={[
            { label: L("cmp_r1"), rec: L("cmp_r1_rec"), reg: L("cmp_r1_reg"), pro: L("cmp_r1_pro") },
            { label: L("cmp_r2"), rec: L("cmp_r2_rec"), reg: L("cmp_r2_reg"), pro: L("cmp_r2_pro") },
            { label: L("cmp_r3"), rec: L("cmp_r3_rec"), reg: L("cmp_r3_reg"), pro: L("cmp_r3_pro") },
          ]}
        />

        {/* 7. Erros frequentes */}
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

        {/* 8. Checklist */}
        <Checklist title={L("chk_title")} items={[L("chk1"), L("chk2"), L("chk3"), L("chk4"), L("chk5")]} />

        {/* 9. Treino específico da aula */}
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

        {/* 10. Resumo */}
        <Takeaways title={L("takeaways_title")} items={[L("t1"), L("t2"), L("t3"), L("t4")]} />

        {/* 11. Glossário */}
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

        {/* 12. Como o GrindLab identifica */}
        <GrindLabDetects
          title={L("gl_title")}
          intro={L("gl_intro")}
          items={[L("gl1"), L("gl2"), L("gl3"), L("gl4"), L("gl5")]}
        />

        {/* 13. Próximos estudos */}
        <NextStep to="/training" label={L("next_label")} sub={L("next_sub")} />
      </article>
    </HudLayout>
  );
}
