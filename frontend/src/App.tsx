import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { urlDeLoginPara, destinoSeguro } from "@/lib/destinoAposLogin";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/lib/auth";
import { FeedbackWidget } from "@/components/hud/FeedbackWidget";
import { CookieConsent } from "@/components/hud/CookieConsent";
import { UploadQueueProvider } from "@/components/hud/UploadQueue";
import Landing from "./pages/Landing.tsx";
import Privacy from "./pages/Privacy.tsx";
import Index from "./pages/Index.tsx";
import Login from "./pages/Login.tsx";
import Tournaments from "./pages/Tournaments.tsx";
import TournamentDetail from "./pages/TournamentDetail.tsx";
import Replayer from "./pages/Replayer.tsx";
import Demo from "./pages/Demo.tsx";
import CoachReplay from "./pages/CoachReplay.tsx";
import Rating from "./pages/Rating.tsx";
import DocsRating from "./pages/DocsRating.tsx";
import Leaderboard from "./pages/Leaderboard.tsx";
import AICoach from "./pages/AICoach.tsx";
import StudyPlan from "./pages/StudyPlan.tsx";
import NotFound from "./pages/NotFound.tsx";
import CoachDashboard from "./pages/coach/CoachDashboard.tsx";
import StudentDetail from "./pages/coach/StudentDetail.tsx";
import CoachProfile from "./pages/coach/CoachProfile.tsx";
import StudentProfile from "./pages/StudentProfile.tsx";
import CoachesDirectory from "./pages/CoachesDirectory.tsx";
import PublicCoachProfile from "./pages/PublicCoachProfile.tsx";
import AdminDashboard from "./pages/admin/AdminDashboard.tsx";
import Fundadores from "./pages/Fundadores.tsx";
import GhostTable from "./pages/GhostTable.tsx";
import Training from "./pages/Training.tsx";
import TrainingV2 from "./pages/TrainingV2.tsx";
import Evolution from "./pages/Evolution.tsx";
import Academy from "./pages/Academy.tsx";
import Ranges from "./pages/Ranges.tsx";
import AcademyMath from "./pages/AcademyMath.tsx";
import AcademyBoardStrength from "./pages/AcademyBoardStrength.tsx";
import AcademyMathIntermediate from "./pages/AcademyMathIntermediate.tsx";
import AcademyTournament from "./pages/AcademyTournament.tsx";
import AcademyGtoPreflop from "./pages/AcademyGtoPreflop.tsx";
import AcademyMultiway from "./pages/AcademyMultiway.tsx";
import AcademyIcm from "./pages/AcademyIcm.tsx";
import AcademyPostflop from "./pages/AcademyPostflop.tsx";
import AcademyBetSizing from "./pages/AcademyBetSizing.tsx";
import AcademyMdf from "./pages/AcademyMdf.tsx";
import AcademyCombos from "./pages/AcademyCombos.tsx";
import AcademyBlockers from "./pages/AcademyBlockers.tsx";
import AcademyPosition from "./pages/AcademyPosition.tsx";
import AcademyShowdown from "./pages/AcademyShowdown.tsx";
import AcademyExploits from "./pages/AcademyExploits.tsx";
import AcademyPko from "./pages/AcademyPko.tsx";
import AcademyImbalances from "./pages/AcademyImbalances.tsx";
import AcademyPushFold from "./pages/AcademyPushFold.tsx";
import AcademyDraws from "./pages/AcademyDraws.tsx";
import AcademyThreeBet from "./pages/AcademyThreeBet.tsx";
import AcademyBarrels from "./pages/AcademyBarrels.tsx";
import AcademyTerms from "./pages/AcademyTerms.tsx";
import AcademyBankroll from "./pages/AcademyBankroll.tsx";
import AcademyBlindWar from "./pages/AcademyBlindWar.tsx";
import LeakTrainer from "./pages/LeakTrainer.tsx";
import Grind from "./pages/Grind.tsx";
import TournamentCompare from "./pages/TournamentCompare.tsx";
import CoachApply from "./pages/CoachApply.tsx";
import Docs from "./pages/Docs.tsx";
import HandBuilder from "./pages/HandBuilder.tsx";
import Subscription from "./pages/Subscription.tsx";

const queryClient = new QueryClient();

const LoadingScreen = () => (
  <div className="min-h-dvh bg-background flex items-center justify-center">
    <span className="font-mono text-xs text-muted-foreground uppercase tracking-widest-2 animate-pulse">
      Carregando…
    </span>
  </div>
);

/**
 * Rota pública: redireciona usuários já logados.
 *
 * É ESTE o guarda que decide para onde a pessoa vai depois de autenticar — ele envolve o
 * `/login` e dispara no instante em que a sessão nasce, vencendo a navegação da própria página.
 * Consertar só os guardas privados deixava o `?next=` sem efeito: verificado no navegador, o
 * clique de e-mail chegava ao login com o destino preservado e terminava em `/admin` mesmo
 * assim. Cinco lugares decidiam destino; o teste unitário passava e o fluxo real não.
 */
function PublicRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const loc = useLocation();
  if (isLoading) return <LoadingScreen />;
  if (user) {
    const destino = destinoSeguro(new URLSearchParams(loc.search).get("next"));
    const porPapel = user.role === "admin" ? "/admin"
      : user.role === "coach" ? "/coach-dashboard" : "/dashboard";
    return <Navigate to={destino ?? porPapel} replace />;
  }
  return <>{children}</>;
}

// COACH-02 P2: o coach é dual-role (aluno + coach). Passou a ter acesso pleno às
// rotas de aluno (upload/treino/dashboard) — não é mais redirecionado p/ o cockpit.
// `allowCoachWithStudent` virou no-op (mantido p/ compat das chamadas existentes).
/**
 * Para onde mandar quem não está autenticado, PRESERVANDO o destino.
 *
 * Os quatro guardas faziam `<Navigate to="/login" replace />` e o destino era descartado — o que
 * quebrava todo CTA de e-mail, já que o token vive em `sessionStorage` (por aba) e link de
 * e-mail abre aba nova. Regra do projeto: mesma regra em N lugares vira função.
 */
function useLoginComDestino() {
  const loc = useLocation();
  return urlDeLoginPara(loc.pathname, loc.search);
}

function ProtectedRoute({ children }: { children: ReactNode; allowCoachWithStudent?: boolean }) {
  const { user, isLoading } = useAuth();
  const paraLogin = useLoginComDestino();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to={paraLogin} replace />;
  return <>{children}</>;
}

function CoachRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const paraLogin = useLoginComDestino();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to={paraLogin} replace />;
  if (user.role !== "coach") return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const paraLogin = useLoginComDestino();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to={paraLogin} replace />;
  if (user.role !== "admin") return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function AuthRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const paraLogin = useLoginComDestino();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to={paraLogin} replace />;
  return <>{children}</>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <UploadQueueProvider>
          <Routes>
            <Route path="/" element={<PublicRoute><Landing /></PublicRoute>} />
            <Route path="/privacidade" element={<Privacy />} />
            {/* Demonstração pública: sem login, para quem ainda não tem dado nenhum. */}
            <Route path="/demo" element={<Demo />} />
            <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/coach-apply" element={<CoachApply />} />
            {/* Pública de propósito: é o destino do link do Instagram, e quem chega ainda
                não tem conta. Exigir login aqui mataria a candidatura no primeiro clique. */}
            <Route path="/fundadores" element={<Fundadores />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Index />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tournaments"
              element={
                <ProtectedRoute>
                  <Tournaments />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tournaments/compare"
              element={
                <ProtectedRoute>
                  <TournamentCompare />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tournaments/:id"
              element={
                <ProtectedRoute allowCoachWithStudent>
                  <TournamentDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/replayer"
              element={
                <AuthRoute>
                  <Replayer />
                </AuthRoute>
              }
            />
            <Route
              path="/coach-replay/:tournamentId"
              element={
                <ProtectedRoute>
                  <CoachReplay />
                </ProtectedRoute>
              }
            />
            <Route
              path="/rating"
              element={
                <ProtectedRoute>
                  <Rating />
                </ProtectedRoute>
              }
            />
            <Route
              path="/docs/rating"
              element={
                <ProtectedRoute>
                  <DocsRating />
                </ProtectedRoute>
              }
            />
            <Route
              path="/leaderboard"
              element={
                <ProtectedRoute>
                  <Leaderboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/study"
              element={
                <ProtectedRoute>
                  <StudyPlan />
                </ProtectedRoute>
              }
            />
            <Route
              path="/hand-builder"
              element={
                <ProtectedRoute>
                  <HandBuilder />
                </ProtectedRoute>
              }
            />
            <Route
              path="/subscription"
              element={
                <ProtectedRoute>
                  <Subscription />
                </ProtectedRoute>
              }
            />
            <Route
              path="/coach"
              element={
                <ProtectedRoute>
                  <AICoach />
                </ProtectedRoute>
              }
            />
            <Route
              path="/coach-dashboard"
              element={
                <CoachRoute>
                  <CoachDashboard />
                </CoachRoute>
              }
            />
            <Route
              path="/coach-dashboard/student/:id"
              element={
                <CoachRoute>
                  <StudentDetail />
                </CoachRoute>
              }
            />
            <Route
              path="/coach-dashboard/profile"
              element={
                <CoachRoute>
                  <CoachProfile />
                </CoachRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <StudentProfile />
                </ProtectedRoute>
              }
            />
            <Route
              path="/coaches"
              element={
                <AuthRoute>
                  <CoachesDirectory />
                </AuthRoute>
              }
            />
            <Route
              path="/coaches/:id"
              element={
                <AuthRoute>
                  <PublicCoachProfile />
                </AuthRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <AdminRoute>
                  <AdminDashboard />
                </AdminRoute>
              }
            />
            <Route
              path="/ghost"
              element={
                <ProtectedRoute>
                  <GhostTable />
                </ProtectedRoute>
              }
            />
            {/* Sparring removido do produto até termos o arco sintético funcional (opção 2). */}
            {/* REVERTIDA (28/08): a CLÁSSICA volta a ser a tela de treino, por decisão do dono
                ("a tela de treino padrão tem que voltar a ser a clássica, oculte a versão beta,
                pois a princípio não iremos mais utilizar").

                A Trilha (cockpit v3) tinha sido promovida em 20/08. Ela não foi apagada: continua
                em `/training/trilha`, sem link em lugar nenhum, para o código não morrer enquanto
                a decisão for "a princípio". Apagar agora tornaria caro voltar atrás de uma escolha
                que o próprio dono marcou como provisória.

                `/training-v2` continua REDIRECIONANDO para `/training`: bookmarks e links de
                e-mail do beta apontam para lá e não podem cair num 404. Só que agora chegam na
                clássica, que é o destino certo. */}
            <Route
              path="/training"
              element={
                <ProtectedRoute>
                  <Training />
                </ProtectedRoute>
              }
            />
            {/* Aliases da clássica: `/training/classic` existia e pode estar em link antigo. */}
            <Route path="/training/classic" element={<Navigate to="/training" replace />} />
            <Route
              path="/training/trilha"
              element={
                <ProtectedRoute>
                  <TrainingV2 />
                </ProtectedRoute>
              }
            />
            <Route path="/training-v2" element={<Navigate to="/training" replace />} />
            <Route path="/evolucao" element={<ProtectedRoute><Evolution /></ProtectedRoute>} />
            {/* Retrato congelado — MESMA tela, dado de outro dia. Comparar meses exige a mesma
                forma, senão o que salta aos olhos é a diferença do desenho, não a do jogo. */}
            <Route path="/evolucao/:reportId" element={<ProtectedRoute><Evolution /></ProtectedRoute>} />
            <Route path="/ranges" element={<ProtectedRoute><Ranges /></ProtectedRoute>} />
            <Route path="/academy" element={<ProtectedRoute><Academy /></ProtectedRoute>} />
            <Route path="/academy/math" element={<ProtectedRoute><AcademyMath /></ProtectedRoute>} />
            <Route path="/academy/math/intermediate" element={<ProtectedRoute><AcademyMathIntermediate /></ProtectedRoute>} />
            <Route path="/academy/board-strength" element={<ProtectedRoute><AcademyBoardStrength /></ProtectedRoute>} />
            <Route path="/academy/tournament" element={<ProtectedRoute><AcademyTournament /></ProtectedRoute>} />
            <Route path="/academy/gto-preflop" element={<ProtectedRoute><AcademyGtoPreflop /></ProtectedRoute>} />
            <Route path="/academy/multiway" element={<ProtectedRoute><AcademyMultiway /></ProtectedRoute>} />
            <Route path="/academy/icm" element={<ProtectedRoute><AcademyIcm /></ProtectedRoute>} />
            <Route path="/academy/postflop" element={<ProtectedRoute><AcademyPostflop /></ProtectedRoute>} />
            <Route path="/academy/bet-sizing" element={<ProtectedRoute><AcademyBetSizing /></ProtectedRoute>} />
            <Route path="/academy/mdf" element={<ProtectedRoute><AcademyMdf /></ProtectedRoute>} />
            <Route path="/academy/combos" element={<ProtectedRoute><AcademyCombos /></ProtectedRoute>} />
            <Route path="/academy/blockers" element={<ProtectedRoute><AcademyBlockers /></ProtectedRoute>} />
            <Route path="/academy/position" element={<ProtectedRoute><AcademyPosition /></ProtectedRoute>} />
            <Route path="/academy/showdown" element={<ProtectedRoute><AcademyShowdown /></ProtectedRoute>} />
            <Route path="/academy/exploits" element={<ProtectedRoute><AcademyExploits /></ProtectedRoute>} />
            <Route path="/academy/pko" element={<ProtectedRoute><AcademyPko /></ProtectedRoute>} />
            <Route path="/academy/imbalances" element={<ProtectedRoute><AcademyImbalances /></ProtectedRoute>} />
            <Route path="/academy/push-fold" element={<ProtectedRoute><AcademyPushFold /></ProtectedRoute>} />
            <Route path="/academy/draws" element={<ProtectedRoute><AcademyDraws /></ProtectedRoute>} />
            <Route path="/academy/3bet" element={<ProtectedRoute><AcademyThreeBet /></ProtectedRoute>} />
            <Route path="/academy/barrels" element={<ProtectedRoute><AcademyBarrels /></ProtectedRoute>} />
            <Route path="/academy/terms" element={<ProtectedRoute><AcademyTerms /></ProtectedRoute>} />
            <Route path="/academy/bankroll" element={<ProtectedRoute><AcademyBankroll /></ProtectedRoute>} />
            <Route path="/academy/blind-war" element={<ProtectedRoute><AcademyBlindWar /></ProtectedRoute>} />
            <Route path="/leak-trainer" element={<ProtectedRoute><LeakTrainer /></ProtectedRoute>} />
            <Route path="/grind" element={<ProtectedRoute><Grind /></ProtectedRoute>} />
            <Route path="/docs" element={<AuthRoute><Docs /></AuthRoute>} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
          <FeedbackWidget />
          <CookieConsent />
          </UploadQueueProvider>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
