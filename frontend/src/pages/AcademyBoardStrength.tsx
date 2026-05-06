import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Layers } from "lucide-react";
import AcademyQuizPage from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";

export default function AcademyBoardStrength() {
  const { t } = useTranslation("academy");
  const loadFn   = useCallback(() => academy.boardStrengthQuestion(), []);
  const submitFn = useCallback(
    (idx: number, ci: number, xp: number) => { academy.boardStrengthSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );
  return (
    <AcademyQuizPage
      eyebrow={t("board.eyebrow")}
      title={t("board.title")}
      description={t("board.subtitle")}
      theme="primary"
      Icon={Layers}
      loadFn={loadFn}
      submitFn={submitFn}
      showCards
    />
  );
}
