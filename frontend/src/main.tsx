import React, { Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { registerSW } from 'virtual:pwa-register';
import './i18n';
import '@fontsource/noto-sans/latin-400.css';
import '@fontsource/noto-sans/latin-500.css';
import '@fontsource/noto-sans/latin-600.css';
import '@fontsource/noto-sans/latin-700.css';
import '@fontsource/noto-sans-devanagari/devanagari-400.css';
import '@fontsource/noto-sans-tamil/tamil-400.css';
import '@fontsource/noto-sans-bengali/bengali-400.css';
import './styles.css';
import { AppShell } from './components/shell';
import { LoadingBlock } from './components/ui';
import { useAppStore } from './state/store';

const AskPage = React.lazy(() => import('./pages/ask').then((module) => ({ default: module.AskPage })));
const ClassificationPage = React.lazy(() => import('./pages/classification').then((module) => ({ default: module.ClassificationPage })));
const PatentRiskPage = React.lazy(() => import('./pages/patent-risk').then((module) => ({ default: module.PatentRiskPage })));
const AbsPage = React.lazy(() => import('./pages/abs').then((module) => ({ default: module.AbsPage })));
const TkPage = React.lazy(() => import('./pages/tk').then((module) => ({ default: module.TkPage })));
const CasePage = React.lazy(() => import('./pages/case').then((module) => ({ default: module.CasePage })));
const ReceiptPage = React.lazy(() => import('./pages/receipt').then((module) => ({ default: module.ReceiptPage })));
const CorpusPage = React.lazy(() => import('./pages/corpus').then((module) => ({ default: module.CorpusPage })));
const EvalPage = React.lazy(() => import('./pages/eval').then((module) => ({ default: module.EvalPage })));
const AdminPage = React.lazy(() => import('./pages/admin').then((module) => ({ default: module.AdminPage })));
const ComponentsPage = React.lazy(() => import('./pages/components-gallery').then((module) => ({ default: module.ComponentsPage })));

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } });
const mode = import.meta.env.VITE_API_MODE ?? 'mock';

async function bootstrap() {
  if (mode === 'mock') {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass', serviceWorker: { url: '/mockServiceWorker.js' } });
  }
  const { uiLanguage, theme } = useAppStore.getState();
  document.documentElement.lang = uiLanguage;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  registerSW({ immediate: true });
  createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><Suspense fallback={<div className="route-loading"><LoadingBlock /></div>}><Routes><Route element={<AppShell />}><Route index element={<AskPage />} /><Route path="classify" element={<ClassificationPage />} /><Route path="patent-risk" element={<PatentRiskPage />} /><Route path="abs" element={<AbsPage />} /><Route path="tk" element={<TkPage />} /><Route path="case" element={<CasePage />} /><Route path="receipt/:id" element={<ReceiptPage />} /><Route path="corpus" element={<CorpusPage />} /><Route path="eval" element={<EvalPage />} /><Route path="admin/escalations" element={<AdminPage />} /><Route path="dev/components" element={<ComponentsPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></Suspense></BrowserRouter></QueryClientProvider></React.StrictMode>);
}
void bootstrap();
