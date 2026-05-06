import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { TrendingUp } from "lucide-react";
import AcademyQuizPage from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";

export default function AcademyTournament() {
  const { t } = useTranslation("academy");
  const loadFn   = useCallback(() => academy.tournamentQuestion(), []);
  const submitFn = useCallback(
    (idx: number, ci: number, xp: number) => { academy.tournamentSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );
  return (
    <AcademyQuizPage
      eyebrow={t("tournament.eyebrow")}
      title={t("tournament.title")}
      description={t("tournament.subtitle")}
      theme="violet"
      Icon={TrendingUp}
      loadFn={loadFn}
      submitFn={submitFn}
    />
  );
}
