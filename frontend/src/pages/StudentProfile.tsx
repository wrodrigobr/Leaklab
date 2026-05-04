import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { KeyRound, Mail, User, UserX, Loader2, Check, AlertTriangle, GraduationCap, Star, Trash2, Users, ChevronRight } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { useAuth } from "@/lib/auth";
import { auth as authApi, student as studentApi, coachDashboard, coaches, profile as profileApi, CoachReview, PublicCoach, DemographicProfile } from "@/lib/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

function StarPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)}>
          <Star className={`size-5 transition-colors ${(hover || value) >= n ? "fill-amber-400 text-amber-400" : "text-muted-foreground"}`} />
        </button>
      ))}
    </div>
  );
}

function CoachReviewWidget({ coachId }: { coachId: number }) {
  const { t } = useTranslation("profile");
  const qc = useQueryClient();
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);

  const { data: existing, isLoading } = useQuery({
    queryKey: ["my-review", coachId],
    queryFn: () => coachDashboard.getMyReview(coachId),
  });

  const save = useMutation({
    mutationFn: () => coachDashboard.submitReview({ rating, review_text: text || undefined, coach_id: coachId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-review", coachId] });
      setEditing(false);
      toast.success(t("coach.reviewSaved"));
    },
  });

  const remove = useMutation({
    mutationFn: () => coachDashboard.deleteMyReview(coachId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-review", coachId] });
      setRating(0); setText(""); setEditing(false);
      toast.success(t("coach.reviewRemoved"));
    },
  });

  if (isLoading) return null;

  const startEdit = (r?: CoachReview | null) => {
    setRating(r?.rating ?? 0);
    setText(r?.review_text ?? "");
    setEditing(true);
  };

  if (existing && !editing) {
    return (
      <div className="rounded-lg border border-border bg-background p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{t("coach.myReview")}</p>
            <div className="flex gap-0.5">
              {[1,2,3,4,5].map(n => <Star key={n} className={`size-3.5 ${existing.rating >= n ? "fill-amber-400 text-amber-400" : "text-border"}`} />)}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => startEdit(existing)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground">{t("coach.editReview")}</button>
            <button onClick={() => remove.mutate()} className="font-mono text-[10px] text-destructive hover:text-destructive/80">
              <Trash2 className="size-3" />
            </button>
          </div>
        </div>
        {existing.review_text && <p className="text-xs text-muted-foreground">{existing.review_text}</p>}
      </div>
    );
  }

  if (editing || !existing) {
    return (
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-3">
        <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {existing ? t("coach.editReviewTitle") : t("coach.rateCoach")}
        </p>
        <StarPicker value={rating} onChange={setRating} />
        <textarea
          rows={2}
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={t("coach.reviewPlaceholder")}
          className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
        <div className="flex gap-2">
          <button
            onClick={() => save.mutate()}
            disabled={rating === 0 || save.isPending}
            className="flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 font-mono text-[11px] font-bold text-primary-foreground disabled:opacity-50"
          >
            {save.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />} {t("coach.submitReview")}
          </button>
          {(existing || editing) && (
            <button onClick={() => setEditing(false)} className="rounded border border-border px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
              {t("coach.cancel")}
            </button>
          )}
        </div>
        {!existing && !editing && (
          <button onClick={() => startEdit()} className="font-mono text-[10px] text-primary hover:underline">{t("coach.addReview")}</button>
        )}
      </div>
    );
  }

  return (
    <button onClick={() => startEdit()} className="font-mono text-[10px] text-primary hover:underline">
      {t("coach.rateMyCoach")}
    </button>
  );
}

// ── BACK-013: Coach discovery when no coach is linked ─────────────────────────

function CoachDiscoveryCard({ coach }: { coach: PublicCoach }) {
  const { t } = useTranslation("profile");
  const r = coach.avg_rating ?? 0;
  return (
    <Link
      to={`/coaches/${coach.user_id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5 hover:border-primary/50 transition-colors"
    >
      {coach.photo_url ? (
        <img src={coach.photo_url} alt={coach.display_name}
          className="size-10 rounded-full object-cover border border-border shrink-0" />
      ) : (
        <div className="size-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
          <GraduationCap className="size-4 text-primary" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-foreground truncate">{coach.display_name || coach.username}</p>
        {coach.stakes && (
          <p className="font-mono text-[9px] text-muted-foreground">{coach.stakes}</p>
        )}
        <div className="flex items-center gap-2 mt-0.5">
          <div className="flex gap-0.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star key={n} className={cn("size-2.5", r >= n ? "fill-amber-400 text-amber-400" : "text-border")} />
            ))}
          </div>
          <span className="font-mono text-[9px] text-muted-foreground flex items-center gap-0.5">
            <Users className="size-2.5" /> {t("coach.students", { n: coach.student_count })}
          </span>
        </div>
      </div>
      <ChevronRight className="size-4 text-muted-foreground shrink-0" />
    </Link>
  );
}

function NoCoachDiscovery() {
  const { t } = useTranslation("profile");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { refreshUser } = useAuth();
  const [inviteKey, setInviteKey] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data } = useQuery({
    queryKey: ["coaches-top"],
    queryFn: () => coaches.list({ sort: "rating", limit: 3 }),
    staleTime: 60_000,
  });

  const linkMut = useMutation({
    mutationFn: () => studentApi.linkCoach(inviteKey),
    onSuccess: async (data) => {
      toast.success(t("coach.linkedSuccess", { name: data.coach.username }));
      await refreshUser();
      qc.invalidateQueries({ queryKey: ["coaches-top"] });
      navigate("/profile");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const topCoaches = data?.coaches ?? [];

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("coach.noCoachDesc")}</p>

      {topCoaches.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("coach.topCoaches")}
          </p>
          <div className="space-y-2">
            {topCoaches.map((c) => <CoachDiscoveryCard key={c.user_id} coach={c} />)}
          </div>
          <Link
            to="/coaches"
            className="font-mono text-[10px] text-primary hover:underline flex items-center gap-1"
          >
            {t("coach.viewAll")}
          </Link>
        </div>
      )}

      {showForm ? (
        <div className="space-y-2 border-t border-border pt-3">
          <p className="font-mono text-[10px] text-muted-foreground">{t("coach.inviteHint")}</p>
          <input
            type="text"
            value={inviteKey}
            onChange={(e) => setInviteKey(e.target.value)}
            placeholder={t("coach.invitePlaceholder")}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
          <div className="flex gap-2">
            <button
              onClick={() => linkMut.mutate()}
              disabled={!inviteKey || linkMut.isPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {linkMut.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              {t("coach.linkBtn")}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("coach.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
        >
          <GraduationCap className="size-3.5" /> {t("coach.hasInvite")}
        </button>
      )}
    </div>
  );
}

function Section({ icon: Icon, title, children }: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-6 space-y-4">
      <div className="flex items-center gap-2.5">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="size-4" />
        </span>
        <h2 className="text-sm font-bold uppercase tracking-widest-2 text-foreground">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

export default function StudentProfile() {
  const { user, refreshUser } = useAuth();
  const { t } = useTranslation("profile");
  const navigate = useNavigate();
  const qc = useQueryClient();

  // ── Dados do Jogador (demográficos + telefone) ────────────────────────────
  const { data: demographics, isLoading: demoLoading } = useQuery({
    queryKey: ["my-demographics"],
    queryFn: () => profileApi.get(),
  });

  const [demoForm, setDemoForm] = useState<Partial<DemographicProfile>>({});
  const [phone, setPhone]       = useState(user?.whatsapp_phone ?? "");
  const [demoSaving, setDemoSaving] = useState(false);

  useEffect(() => {
    if (demographics) setDemoForm(demographics);
  }, [demographics]);

  useEffect(() => {
    setPhone(user?.whatsapp_phone ?? "");
  }, [user?.whatsapp_phone]);

  const CORE_DEMO_FIELDS = ["birth_year", "country", "poker_experience_years", "main_game_type", "usual_buyin_range"] as const;
  const demoFilledCount = CORE_DEMO_FIELDS.filter((f) => {
    const v = demoForm[f as keyof DemographicProfile];
    return v !== null && v !== undefined && v !== "";
  }).length;

  const handleSaveDemographics = async (e: React.FormEvent) => {
    e.preventDefault();
    setDemoSaving(true);
    try {
      await profileApi.update(demoForm);
      await authApi.updatePhone(phone.trim() || null);
      qc.invalidateQueries({ queryKey: ["my-demographics"] });
      await refreshUser();
      toast.success(t("demo.saved"));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t("demo.saved"));
    } finally {
      setDemoSaving(false);
    }
  };

  // ── Alterar e-mail ────────────────────────────────────────────────────────
  const [newEmail, setNewEmail]         = useState(user?.email ?? "");
  const [emailPw, setEmailPw]           = useState("");
  const [emailLoading, setEmailLoading] = useState(false);

  const handleUpdateEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.includes("@")) { toast.error(t("email.invalid")); return; }
    setEmailLoading(true);
    try {
      await authApi.updateEmail(newEmail, emailPw);
      await refreshUser();
      setEmailPw("");
      toast.success(t("email.success"));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t("email.error"));
    } finally {
      setEmailLoading(false);
    }
  };

  // ── Trocar senha ──────────────────────────────────────────────────────────
  const [currentPw,  setCurrentPw]  = useState("");
  const [newPw,      setNewPw]      = useState("");
  const [confirmPw,  setConfirmPw]  = useState("");
  const [pwLoading,  setPwLoading]  = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw.length < 8) { toast.error(t("password.minLength")); return; }
    if (newPw !== confirmPw) { toast.error(t("password.mismatch")); return; }
    setPwLoading(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      toast.success(t("password.success"));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t("password.error"));
    } finally {
      setPwLoading(false);
    }
  };

  // ── Desvincular coach ─────────────────────────────────────────────────────
  const [unlinkLoading, setUnlinkLoading] = useState(false);
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const [unlinkPw, setUnlinkPw] = useState("");

  const handleUnlink = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!confirmUnlink) { setConfirmUnlink(true); return; }
    if (!unlinkPw) { toast.error(t("coach.unlinkPwRequired")); return; }
    setUnlinkLoading(true);
    try {
      await studentApi.unlinkCoach(unlinkPw);
      await refreshUser();
      setConfirmUnlink(false);
      setUnlinkPw("");
      toast.success(t("coach.unlinkSuccess"));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t("coach.unlinkError"));
    } finally {
      setUnlinkLoading(false);
    }
  };

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-2xl px-6 py-10 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
          <p className="font-mono text-[11px] text-muted-foreground mt-1">{user?.username}</p>
        </div>

        {/* Dados do Jogador */}
        <Section icon={User} title={t("demo.title")}>
          {/* Completion bar */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
              <div
                className={cn("h-full transition-all", demoFilledCount >= 5 ? "bg-emerald-500" : "bg-primary")}
                style={{ width: `${(demoFilledCount / 5) * 100}%` }}
              />
            </div>
            <span className={cn("font-mono text-[10px] shrink-0", demoFilledCount >= 5 ? "text-emerald-400" : "text-muted-foreground")}>
              {demoFilledCount >= 5 ? t("demo.completionDone") : t("demo.completion", { n: demoFilledCount })}
            </span>
          </div>

          <p className="text-xs text-muted-foreground">{t("demo.desc")}</p>

          {demoLoading ? (
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          ) : (
            <form onSubmit={handleSaveDemographics} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label={t("demo.birthYear")}>
                  <input
                    type="number"
                    min={1940}
                    max={2015}
                    value={demoForm.birth_year ?? ""}
                    onChange={(e) => setDemoForm((p) => ({ ...p, birth_year: e.target.value ? Number(e.target.value) : null }))}
                    placeholder="1990"
                    className={inputCls}
                  />
                </Field>
                <Field label={t("demo.experienceYears")}>
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={demoForm.poker_experience_years ?? ""}
                    onChange={(e) => setDemoForm((p) => ({ ...p, poker_experience_years: e.target.value ? Number(e.target.value) : null }))}
                    placeholder="3"
                    className={inputCls}
                  />
                </Field>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label={t("demo.gameType")}>
                  <select
                    value={demoForm.main_game_type ?? ""}
                    onChange={(e) => setDemoForm((p) => ({ ...p, main_game_type: (e.target.value as DemographicProfile["main_game_type"]) || null }))}
                    className={inputCls}
                  >
                    <option value="">{t("demo.selectPlaceholder")}</option>
                    <option value="mtt">{t("demo.gameTypes.mtt")}</option>
                    <option value="cash">{t("demo.gameTypes.cash")}</option>
                    <option value="spin">{t("demo.gameTypes.spin")}</option>
                    <option value="mixed">{t("demo.gameTypes.mixed")}</option>
                  </select>
                </Field>
                <Field label={t("demo.buyinRange")}>
                  <select
                    value={demoForm.usual_buyin_range ?? ""}
                    onChange={(e) => setDemoForm((p) => ({ ...p, usual_buyin_range: (e.target.value as DemographicProfile["usual_buyin_range"]) || null }))}
                    className={inputCls}
                  >
                    <option value="">{t("demo.selectPlaceholder")}</option>
                    <option value="micro">{t("demo.buyinRanges.micro")}</option>
                    <option value="low">{t("demo.buyinRanges.low")}</option>
                    <option value="mid">{t("demo.buyinRanges.mid")}</option>
                    <option value="high">{t("demo.buyinRanges.high")}</option>
                  </select>
                </Field>
              </div>

              <Field label={t("demo.country")}>
                <input
                  type="text"
                  value={demoForm.country ?? ""}
                  onChange={(e) => setDemoForm((p) => ({ ...p, country: e.target.value || null }))}
                  placeholder="Brasil"
                  className={inputCls}
                />
              </Field>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label={t("demo.stateProvince")}>
                  <input
                    type="text"
                    value={demoForm.state_province ?? ""}
                    onChange={(e) => setDemoForm((p) => ({ ...p, state_province: e.target.value || null }))}
                    placeholder="SP"
                    className={inputCls}
                  />
                </Field>
                <Field label={t("demo.city")}>
                  <input
                    type="text"
                    value={demoForm.city ?? ""}
                    onChange={(e) => setDemoForm((p) => ({ ...p, city: e.target.value || null }))}
                    placeholder="São Paulo"
                    className={inputCls}
                  />
                </Field>
              </div>

              <Field label={t("demo.phone")}>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder={t("demo.phonePlaceholder")}
                  className={inputCls}
                />
              </Field>

              <button
                type="submit"
                disabled={demoSaving}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {demoSaving ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
                {t("demo.save")}
              </button>
            </form>
          )}
        </Section>

        {/* Alterar e-mail */}
        <Section icon={Mail} title={t("fields.email")}>
          <form onSubmit={handleUpdateEmail} className="space-y-3">
            <Field label={t("email.newLabel")}>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className={inputCls}
                required
              />
            </Field>
            <Field label={t("email.confirmPwLabel")}>
              <input
                type="password"
                value={emailPw}
                onChange={(e) => setEmailPw(e.target.value)}
                placeholder={t("email.currentPwPlaceholder")}
                className={inputCls}
                required
              />
            </Field>
            <button
              type="submit"
              disabled={emailLoading}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {emailLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              {t("email.save")}
            </button>
          </form>
        </Section>

        {/* Trocar senha */}
        <Section icon={KeyRound} title={t("password.change")}>
          <form onSubmit={handleChangePassword} className="space-y-3">
            <Field label={t("password.currentLabel")}>
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                placeholder={t("password.currentPlaceholder")}
                className={inputCls}
                required
              />
            </Field>
            <Field label={t("password.newLabel")}>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                placeholder={t("password.newPlaceholder")}
                className={inputCls}
                required
                minLength={8}
              />
            </Field>
            <Field label={t("password.confirmLabel")}>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                placeholder={t("password.confirmPlaceholder")}
                className={inputCls}
                required
              />
            </Field>
            {newPw && confirmPw && newPw !== confirmPw && (
              <p className="font-mono text-[10px] text-destructive flex items-center gap-1">
                <AlertTriangle className="size-3" /> {t("password.mismatch")}
              </p>
            )}
            <button
              type="submit"
              disabled={pwLoading}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {pwLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              {t("password.save")}
            </button>
          </form>
        </Section>

        {/* Vínculo com coach */}
        <Section icon={GraduationCap} title={t("sections.coach")}>
          {user?.coach_id ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
                <GraduationCap className="size-4 text-primary shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-foreground">{user.coach_username}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{t("coach.linked")}</p>
                </div>
              </div>
              <CoachReviewWidget coachId={user.coach_id} />

              {!confirmUnlink ? (
                <button
                  onClick={handleUnlink}
                  className="inline-flex items-center gap-2 rounded-md border border-destructive/40 px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <UserX className="size-3.5" /> {t("coach.unlink")}
                </button>
              ) : (
                <form onSubmit={handleUnlink} className="space-y-3">
                  <p className="font-mono text-[11px] text-destructive flex items-center gap-1.5">
                    <AlertTriangle className="size-3.5" />
                    {t("coach.unlinkConfirmMsg", { name: user.coach_username })}
                  </p>
                  <Field label={t("coach.unlinkPwLabel")}>
                    <input
                      type="password"
                      value={unlinkPw}
                      onChange={(e) => setUnlinkPw(e.target.value)}
                      placeholder={t("password.currentPlaceholder")}
                      className={inputCls}
                      autoFocus
                      required
                    />
                  </Field>
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={unlinkLoading}
                      className="inline-flex items-center gap-2 rounded-md bg-destructive px-4 py-2 font-mono text-[11px] font-bold uppercase text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
                    >
                      {unlinkLoading ? <Loader2 className="size-3.5 animate-spin" /> : <UserX className="size-3.5" />}
                      {t("coach.unlinkConfirm")}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setConfirmUnlink(false); setUnlinkPw(""); }}
                      className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {t("coach.cancel")}
                    </button>
                  </div>
                </form>
              )}
            </div>
          ) : (
            <NoCoachDiscovery />
          )}
        </Section>
      </main>
    </div>
  );
}
