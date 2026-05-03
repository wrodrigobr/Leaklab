import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Star, Users, DollarSign, Globe, GraduationCap,
  CheckCircle2, Loader2, Youtube, Twitch, Twitter, ExternalLink,
  Mail, Calendar, Zap, Trophy, MessageSquare, Trash2,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { coaches, coachDashboard, student, PublicCoach, PublicCoachReview } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// ── Star helpers ──────────────────────────────────────────────────────────────

function StarRow({ rating, count, size = "sm" }: { rating: number | null; count: number; size?: "sm" | "lg" }) {
  const r = rating ?? 0;
  const s = size === "lg" ? "size-4" : "size-3";
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <Star key={n} className={cn(s, r >= n ? "fill-amber-400 text-amber-400" : "text-border")} />
        ))}
      </div>
      <span className="font-mono text-xs text-muted-foreground">
        {r > 0 ? r.toFixed(1) : "—"} ({count} avaliações)
      </span>
    </div>
  );
}

function RatingBar({ label, count, total }: { label: string; count: number; total: number }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-[10px] w-3 text-muted-foreground">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
        <div className="h-full rounded-full bg-amber-400 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[10px] w-5 text-right text-muted-foreground">{count}</span>
    </div>
  );
}

// ── Review form ───────────────────────────────────────────────────────────────

function StarPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange(n)}
        >
          <Star className={cn(
            "size-5 transition-colors",
            (hover || value) >= n ? "fill-amber-400 text-amber-400" : "text-border"
          )} />
        </button>
      ))}
    </div>
  );
}

function ReviewCard({ review, onDelete }: { review: PublicCoachReview; onDelete?: () => void }) {
  const r = review.rating;
  return (
    <div className="rounded-lg border border-border bg-background p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-foreground">{review.username}</span>
          <div className="flex gap-0.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star key={n} className={cn("size-3", r >= n ? "fill-amber-400 text-amber-400" : "text-border")} />
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-muted-foreground">
            {new Date(review.updated_at).toLocaleDateString("pt-BR")}
          </span>
          {onDelete && (
            <button onClick={onDelete} className="text-muted-foreground hover:text-destructive transition-colors">
              <Trash2 className="size-3.5" />
            </button>
          )}
        </div>
      </div>
      {review.review_text && (
        <p className="text-xs text-muted-foreground">{review.review_text}</p>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PublicCoachProfile() {
  const { id } = useParams<{ id: string }>();
  const coachId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useTranslation("coaches");
  const { t: tc } = useTranslation("common");
  const qc = useQueryClient();
  const isStudent = user?.role === "player";
  const hasCoach = !!user?.coach_id;

  const [rating, setRating] = useState(0);
  const [reviewText, setReviewText] = useState("");
  const [linkKey, setLinkKey] = useState("");
  const [showLinkForm, setShowLinkForm] = useState(false);

  const { data: profileData, isLoading } = useQuery({
    queryKey: ["public-coach", coachId],
    queryFn: () => coaches.get(coachId),
    enabled: !!coachId,
  });

  const { data: myReview } = useQuery({
    queryKey: ["my-review", coachId],
    queryFn: () => coachDashboard.getMyReview(coachId),
    enabled: isStudent,
  });

  const submitReviewMut = useMutation({
    mutationFn: () => coachDashboard.submitReview({ rating, review_text: reviewText || undefined, coach_id: coachId }),
    onSuccess: () => {
      toast.success("Avaliação enviada!");
      qc.invalidateQueries({ queryKey: ["public-coach", coachId] });
      qc.invalidateQueries({ queryKey: ["my-review", coachId] });
      setRating(0);
      setReviewText("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteReviewMut = useMutation({
    mutationFn: () => coachDashboard.deleteMyReview(coachId),
    onSuccess: () => {
      toast.success("Avaliação removida.");
      qc.invalidateQueries({ queryKey: ["public-coach", coachId] });
      qc.invalidateQueries({ queryKey: ["my-review", coachId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const linkMut = useMutation({
    mutationFn: () => student.linkCoach(linkKey),
    onSuccess: (data) => {
      toast.success(`Vinculado ao coach ${data.coach.username}!`);
      navigate("/profile");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="min-h-dvh bg-background">
        <HudHeader />
        <div className="flex items-center justify-center py-32 text-muted-foreground gap-2">
          <Loader2 className="size-5 animate-spin" /> {tc("actions.loading")}
        </div>
      </div>
    );
  }

  const c = profileData as PublicCoach | undefined;
  if (!c) {
    return (
      <div className="min-h-dvh bg-background">
        <HudHeader />
        <div className="flex flex-col items-center justify-center py-32 gap-3 text-muted-foreground">
          <GraduationCap className="size-10 opacity-30" />
          <p className="text-sm">{tc("errors.notFound")}</p>
          <Link to="/coaches" className="font-mono text-xs text-primary hover:underline">{t("profile.back")}</Link>
        </div>
      </div>
    );
  }

  const reviews = (c.reviews ?? []) as PublicCoachReview[];
  const totalReviews = c.review_count;
  const avgRating = c.avg_rating ?? 0;
  const countByStars = [5, 4, 3, 2, 1].map((star) => ({
    star,
    count: reviews.filter((r) => r.rating === star).length,
  }));

  const myReviewData = myReview as PublicCoachReview | null | undefined;

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-5xl px-6 py-8 space-y-6">
        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" /> {tc("actions.back")}
        </button>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left — profile card */}
          <div className="lg:col-span-1 space-y-4">
            {/* Avatar + name */}
            <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
              <div className="flex flex-col items-center text-center gap-3">
                {c.photo_url ? (
                  <img src={c.photo_url} alt={c.display_name}
                    className="size-20 rounded-full object-cover border-2 border-primary/30" />
                ) : (
                  <div className="size-20 rounded-full bg-primary/10 flex items-center justify-center">
                    <GraduationCap className="size-8 text-primary" />
                  </div>
                )}
                <div>
                  <h1 className="text-xl font-bold text-foreground">
                    {c.display_name || c.username}
                  </h1>
                  {c.stakes && (
                    <p className="font-mono text-[10px] text-muted-foreground mt-0.5">{c.stakes}</p>
                  )}
                  <div className="mt-1.5 flex justify-center">
                    <StarRow rating={c.avg_rating} count={totalReviews} size="sm" />
                  </div>
                </div>
              </div>

              {/* Quick stats */}
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="rounded-md border border-border bg-background p-2">
                  <p className="font-mono text-lg font-bold text-foreground">{c.student_count}</p>
                  <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider">{t("profile.students")}</p>
                </div>
                {c.experience_years != null && (
                  <div className="rounded-md border border-border bg-background p-2">
                    <p className="font-mono text-lg font-bold text-foreground">{c.experience_years}a</p>
                    <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider">Experiência</p>
                  </div>
                )}
              </div>

              {/* Badges */}
              <div className="flex flex-wrap gap-1.5 justify-center">
                {c.trial_available && (
                  <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 font-mono text-[10px] text-primary">
                    <CheckCircle2 className="size-3" /> Trial disponível
                  </span>
                )}
                {c.languages.length > 0 && (
                  <span className="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 font-mono text-[10px] text-muted-foreground">
                    <Globe className="size-3" /> {c.languages.map((l) => l.toUpperCase()).join(" · ")}
                  </span>
                )}
              </div>

              {/* Price */}
              {(c.price_per_session != null || c.price_monthly != null) && (
                <div className="space-y-1 border-t border-border pt-3">
                  {c.price_per_session != null && (
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <DollarSign className="size-3" /> Por sessão
                      </span>
                      <span className="font-mono text-sm font-bold text-foreground">R$ {c.price_per_session}</span>
                    </div>
                  )}
                  {c.price_monthly != null && (
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="size-3" /> Mensalidade
                      </span>
                      <span className="font-mono text-sm font-bold text-foreground">R$ {c.price_monthly}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Contact */}
              <div className="space-y-2 border-t border-border pt-3">
                {c.contact_email && (
                  <a href={`mailto:${c.contact_email}`}
                    className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
                    <Mail className="size-3.5 shrink-0" />
                    <span className="truncate">{c.contact_email}</span>
                  </a>
                )}
                {c.contact_link && (
                  <a href={c.contact_link} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-2 text-xs text-primary hover:underline">
                    <ExternalLink className="size-3.5" /> Contato / WhatsApp
                  </a>
                )}
                <div className="flex gap-3 pt-1">
                  {c.social_youtube && (
                    <a href={c.social_youtube} target="_blank" rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground transition-colors">
                      <Youtube className="size-4" />
                    </a>
                  )}
                  {c.social_twitch && (
                    <a href={c.social_twitch} target="_blank" rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground transition-colors">
                      <Twitch className="size-4" />
                    </a>
                  )}
                  {c.social_twitter && (
                    <a href={c.social_twitter} target="_blank" rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground transition-colors">
                      <Twitter className="size-4" />
                    </a>
                  )}
                </div>
              </div>

              {/* CTA — link with coach */}
              {isStudent && !hasCoach && (
                <div className="border-t border-border pt-3">
                  {showLinkForm ? (
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] text-muted-foreground">
                        Insira a chave de convite do coach para se vincular:
                      </p>
                      <input
                        type="text"
                        value={linkKey}
                        onChange={(e) => setLinkKey(e.target.value)}
                        placeholder="Chave de convite…"
                        className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => linkMut.mutate()}
                          disabled={!linkKey || linkMut.isPending}
                          className="flex-1 rounded bg-primary px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                        >
                          {linkMut.isPending ? <Loader2 className="size-3 animate-spin mx-auto" /> : "Vincular"}
                        </button>
                        <button
                          onClick={() => setShowLinkForm(false)}
                          className="px-3 py-1.5 font-mono text-[10px] text-muted-foreground hover:text-foreground"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setShowLinkForm(true)}
                      className="w-full rounded-md bg-primary px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      Contratar este Coach
                    </button>
                  )}
                </div>
              )}
              {isStudent && hasCoach && user?.coach_id !== coachId && (
                <p className="font-mono text-[10px] text-center text-muted-foreground border-t border-border pt-3">
                  Você já tem um coach vinculado.
                </p>
              )}
            </div>
          </div>

          {/* Right — bio, specialties, results, reviews */}
          <div className="lg:col-span-2 space-y-5">
            {/* Bio */}
            {c.bio && (
              <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-2">
                <h2 className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
                  <GraduationCap className="size-3" /> Sobre
                </h2>
                <p className="text-sm text-foreground leading-relaxed">{c.bio}</p>
              </div>
            )}

            {/* Specialties */}
            {c.specialties.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
                <h2 className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
                  <Zap className="size-3" /> Especialidades
                </h2>
                <div className="flex flex-wrap gap-2">
                  {c.specialties.map((s) => (
                    <span key={s} className="rounded-full bg-primary/10 px-3 py-1 font-mono text-xs text-primary">
                      {s}
                    </span>
                  ))}
                </div>
                {c.coaching_style && (
                  <p className="text-xs text-muted-foreground border-t border-border pt-3">
                    <span className="font-bold text-foreground">Estilo:</span> {c.coaching_style}
                  </p>
                )}
                {c.availability && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Calendar className="size-3" /> {c.availability}
                  </p>
                )}
              </div>
            )}

            {/* Biggest results */}
            {c.biggest_results.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
                <h2 className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
                  <Trophy className="size-3" /> Principais resultados
                </h2>
                <ul className="space-y-2">
                  {c.biggest_results.map((r, i) => (
                    <li key={i} className="flex items-center justify-between rounded-md border border-border bg-background px-3 py-2">
                      <span className="text-sm text-foreground">{r.name}</span>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs text-primary font-bold">{r.prize}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">{r.year}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Ratings distribution */}
            {totalReviews > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
                <h2 className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
                  <Star className="size-3" /> Avaliações
                </h2>
                <div className="flex gap-6 items-center">
                  <div className="text-center shrink-0">
                    <p className="text-4xl font-bold text-foreground">{avgRating.toFixed(1)}</p>
                    <div className="flex justify-center mt-1">
                      <StarRow rating={avgRating} count={totalReviews} />
                    </div>
                  </div>
                  <div className="flex-1 space-y-1.5">
                    {countByStars.map(({ star, count }) => (
                      <RatingBar key={star} label={String(star)} count={count} total={totalReviews} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Submit review */}
            {isStudent && user?.coach_id === coachId && (
              <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
                <h2 className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
                  <MessageSquare className="size-3" /> Sua avaliação
                </h2>
                {myReviewData ? (
                  <ReviewCard
                    review={myReviewData}
                    onDelete={() => deleteReviewMut.mutate()}
                  />
                ) : (
                  <div className="space-y-3">
                    <StarPicker value={rating} onChange={setRating} />
                    <textarea
                      value={reviewText}
                      onChange={(e) => setReviewText(e.target.value)}
                      placeholder="Conte sobre sua experiência (opcional)…"
                      rows={3}
                      className="w-full rounded border border-border bg-background px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                    />
                    <button
                      onClick={() => submitReviewMut.mutate()}
                      disabled={rating === 0 || submitReviewMut.isPending}
                      className="rounded-md bg-primary px-4 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                    >
                      {submitReviewMut.isPending ? <Loader2 className="size-3 animate-spin" /> : "Enviar avaliação"}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Reviews list */}
            {reviews.length > 0 && (
              <div className="space-y-3">
                <h2 className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                  Comentários ({reviews.length})
                </h2>
                {reviews.map((r, i) => (
                  <ReviewCard key={i} review={r} />
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
