import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Calculator } from "lucide-react";
import AcademyQuizPage from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";

export default function AcademyMath() {
  const { t } = useTranslation("academy");
  const loadFn   = useCallback(() => academy.mathQuestion("beginner"), []);
  const submitFn = useCallback(
    (idx: number, ci: number, xp: number) => { academy.mathSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );
  return (
    <AcademyQuizPage
      eyebrow={t("math.eyebrow")}
      title={t("math.title")}
      description={t("math.subtitle")}
      theme="emerald"
      Icon={Calculator}
      loadFn={loadFn}
      submitFn={submitFn}
    />
  );
}
