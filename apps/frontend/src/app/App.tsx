import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../shared/layout/AppShell';
import { RagDashboardPage } from '../pages/RagDashboardPage';
import { RagCreatePage } from '../pages/RagCreatePage';
import { GuidePage } from '../pages/GuidePage';
import { RagDetailPage, RagSetupPage } from '../features/rag/RagWorkspace';

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/rag" element={<RagDashboardPage />} />
        <Route path="/rag/new" element={<RagCreatePage />} />
        <Route path="/rag/:id/setup" element={<RagSetupPage />} />
        <Route path="/rag/:id" element={<RagDetailPage />} />
        <Route path="/guide" element={<GuidePage />} />
        <Route path="*" element={<Navigate to="/rag" replace />} />
      </Route>
    </Routes>
  );
}
