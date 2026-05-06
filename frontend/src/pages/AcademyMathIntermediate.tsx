import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Sigma } from "lucide-react";
import AcademyQuizPage from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";

export default function AcademyMathIntermediate() {
  const { t } = useTranslation("academy");
  const loadFn   = useCallback(() => academy.mathQuestion("intermediate"), []);
  const submitFn = useCallback(
    (idx: number, ci: number, xp: number) => { academy.mathSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );
  return (
    <AcademyQuizPage
      eyebrow={t("mathInt.eyebrow")}
      title={t("mathInt.title")}
      description={t("mathInt.subtitle")}
      theme="amber"
      Icon={Sigma}
      loadFn={loadFn}
      submitFn={submitFn}
    />
  );
}
