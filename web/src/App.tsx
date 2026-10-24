import { Suspense, lazy, useSyncExternalStore } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Skeleton } from "./components/Feedback";
import { Layout } from "./components/Layout";
import { getToken, onAuthChange } from "./lib/auth";
import HomePage from "./pages/HomePage";
import IncidentsPage from "./pages/IncidentsPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import ProductFormPage from "./pages/ProductFormPage";
import SettingsPage from "./pages/SettingsPage";

// The detail page carries the charting library; load it on demand so Home stays fast.
const ProductPage = lazy(() => import("./pages/ProductPage"));

function useToken(): string | null {
  return useSyncExternalStore(onAuthChange, () => getToken());
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useToken();
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route
          path="p/:id"
          element={
            <Suspense fallback={<div className="px-4 pt-28"><Skeleton className="h-64 w-full rounded-[26px]" /></div>}>
              <ProductPage />
            </Suspense>
          }
        />
        <Route path="p/:id/edit" element={<ProductFormPage mode="edit" />} />
        <Route path="new" element={<ProductFormPage mode="create" />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
