import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/lib/auth";
import Landing from "./pages/Landing.tsx";
import Index from "./pages/Index.tsx";
import Login from "./pages/Login.tsx";
import Tournaments from "./pages/Tournaments.tsx";
import TournamentDetail from "./pages/TournamentDetail.tsx";
import Replayer from "./pages/Replayer.tsx";
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
import GhostTable from "./pages/GhostTable.tsx";
import Sparring from "./pages/Sparring.tsx";
import Training from "./pages/Training.tsx";
import Academy from "./pages/Academy.tsx";
import AcademyMath from "./pages/AcademyMath.tsx";
import AcademyBoardStrength from "./pages/AcademyBoardStrength.tsx";
import AcademyMathIntermediate from "./pages/AcademyMathIntermediate.tsx";
import AcademyTournament from "./pages/AcademyTournament.tsx";
import AcademyGtoPreflop from "./pages/AcademyGtoPreflop.tsx";
import TournamentCompare from "./pages/TournamentCompare.tsx";
import CoachApply from "./pages/CoachApply.tsx";
import Docs from "./pages/Docs.tsx";
import HandBuilder from "./pages/HandBuilder.tsx";

const queryClient = new QueryClient();

const LoadingScreen = () => (
  <div className="min-h-dvh bg-background flex items-center justify-center">
    <span className="font-mono text-xs text-muted-foreground uppercase tracking-widest-2 animate-pulse">
      Carregando…
    </span>
  </div>
);

/** Rota pública: redireciona usuários já logados para o dashboard. */
function PublicRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (user) return <Navigate to={user.role === "admin" ? "/admin" : user.role === "coach" ? "/coach-dashboard" : "/dashboard"} replace />;
  return <>{children}</>;
}

function ProtectedRoute({ children, allowCoachWithStudent = false }: { children: ReactNode; allowCoachWithStudent?: boolean }) {
  const { user, isLoading } = useAuth();
  const [sp] = useSearchParams();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "coach") {
    // exceção: coach revisando um aluno (ex.: /tournaments/:id?student=13) entra; senão → dash
    if (allowCoachWithStudent && sp.get("student")) return <>{children}</>;
    return <Navigate to="/coach-dashboard" replace />;
  }
  return <>{children}</>;
}

function CoachRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "coach") return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function AuthRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<PublicRoute><Landing /></PublicRoute>} />
            <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/coach-apply" element={<CoachApply />} />
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
            <Route
              path="/sparring"
              element={
                <ProtectedRoute>
                  <Sparring />
                </ProtectedRoute>
              }
            />
            <Route
              path="/training"
              element={
                <ProtectedRoute>
                  <Training />
                </ProtectedRoute>
              }
            />
            <Route path="/academy" element={<ProtectedRoute><Academy /></ProtectedRoute>} />
            <Route path="/academy/math" element={<ProtectedRoute><AcademyMath /></ProtectedRoute>} />
            <Route path="/academy/math/intermediate" element={<ProtectedRoute><AcademyMathIntermediate /></ProtectedRoute>} />
            <Route path="/academy/board-strength" element={<ProtectedRoute><AcademyBoardStrength /></ProtectedRoute>} />
            <Route path="/academy/tournament" element={<ProtectedRoute><AcademyTournament /></ProtectedRoute>} />
            <Route path="/academy/gto-preflop" element={<ProtectedRoute><AcademyGtoPreflop /></ProtectedRoute>} />
            <Route path="/docs" element={<AuthRoute><Docs /></AuthRoute>} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
