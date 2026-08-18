import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { AppShell } from "@/components/Layout/AppShell";
import { LoginPage } from "@/pages/Login";
import { DashboardPage } from "@/pages/Dashboard";
import { CreateProjectPage } from "@/pages/CreateProject";
import { ProjectWorkspacePage } from "@/pages/ProjectWorkspace";
import { CostAnalyticsPage } from "@/pages/CostAnalytics";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const checkSession = useAuthStore((s) => s.checkSession);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  if (!isInitialized) {
    return <div className="h-screen w-screen flex items-center justify-center text-text-tertiary">Loading...</div>;
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/new" element={<ProtectedRoute><CreateProjectPage /></ProtectedRoute>} />
      <Route path="/projects/:projectId" element={<ProtectedRoute><ProjectWorkspacePage /></ProtectedRoute>} />
      <Route path="/projects/:projectId/analytics" element={<ProtectedRoute><CostAnalyticsPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
