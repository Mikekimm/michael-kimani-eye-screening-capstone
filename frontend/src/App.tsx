import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";

import { AppShell, ProtectedRoute } from "@/components/AppShell";
import { EmptyState, ListSkeleton } from "@/components/feedback";
import { buttonVariants } from "@/components/ui/primitives";
import { ConsentPage, ForgotPasswordPage, LoginPage, ResetPasswordPage, SignupPage } from "@/pages/auth";

// Each area is its own chunk, so a health worker's phone never downloads the admin charts.
const HomePage = lazy(() => import("@/pages/HomePage").then((m) => ({ default: m.HomePage })));
const PatientsPage = lazy(() => import("@/pages/patients").then((m) => ({ default: m.PatientsPage })));
const NewPatientPage = lazy(() => import("@/pages/patients").then((m) => ({ default: m.NewPatientPage })));
const PatientDetailPage = lazy(() => import("@/pages/patients").then((m) => ({ default: m.PatientDetailPage })));
const ScreenPage = lazy(() => import("@/pages/ScreenPage").then((m) => ({ default: m.ScreenPage })));
const ScreeningDetailPage = lazy(() => import("@/pages/ScreeningDetailPage").then((m) => ({ default: m.ScreeningDetailPage })));
const HistoryPage = lazy(() => import("@/pages/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const ReviewQueuePage = lazy(() => import("@/pages/specialist").then((m) => ({ default: m.ReviewQueuePage })));
const CaseReviewPage = lazy(() => import("@/pages/specialist").then((m) => ({ default: m.CaseReviewPage })));
const AnalyticsPage = lazy(() => import("@/pages/admin").then((m) => ({ default: m.AnalyticsPage })));
const UsersPage = lazy(() => import("@/pages/admin").then((m) => ({ default: m.UsersPage })));
const AboutPage = lazy(() => import("@/pages/AboutPage").then((m) => ({ default: m.AboutPage })));

function NotFound() {
  return <EmptyState title="Page not found" action={<Link to="/" className={buttonVariants({ size: "sm" })}>Go home</Link>} />;
}

export function App() {
  return (
    <Suspense fallback={<div className="p-4"><ListSkeleton /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route element={<AppShell />}>
          <Route element={<ProtectedRoute roles={["health_worker"]} />}>
            <Route index element={<HomePage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="patients/new" element={<NewPatientPage />} />
            <Route path="patients/:id" element={<PatientDetailPage />} />
            <Route path="screen" element={<ScreenPage />} />
            <Route path="screenings/:id" element={<ScreeningDetailPage />} />
            <Route path="history" element={<HistoryPage />} />
          </Route>
          <Route element={<ProtectedRoute roles={["specialist"]} />}>
            <Route path="reviews" element={<ReviewQueuePage />} />
            <Route path="reviews/:id" element={<CaseReviewPage />} />
          </Route>
          <Route element={<ProtectedRoute roles={["admin"]} />}>
            <Route path="admin/analytics" element={<AnalyticsPage />} />
            <Route path="admin/users" element={<UsersPage />} />
          </Route>
          <Route element={<ProtectedRoute roles={["health_worker", "specialist", "admin"]} />}>
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
