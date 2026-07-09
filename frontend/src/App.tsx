import { BrowserRouter, Route, Routes, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import NewDiagnosis from '@/pages/NewDiagnosis';
import DiagnosisStatus from '@/pages/DiagnosisStatus';
import ReportView from '@/pages/ReportView';
import ReportList from '@/pages/ReportList';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function Header() {
  return (
    <header className="bg-white border-b">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link to="/" className="text-xl font-bold text-gray-900">
          GEO 诊断 Agent
        </Link>
        <nav className="space-x-4">
          <Link to="/" className="text-gray-600 hover:text-gray-900">历史</Link>
          <Link to="/new" className="px-3 py-1 bg-blue-600 text-white rounded-md">
            新建诊断
          </Link>
        </nav>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Header />
        <Routes>
          <Route path="/" element={<ReportList />} />
          <Route path="/new" element={<NewDiagnosis />} />
          <Route path="/diagnosis/:taskId/status" element={<DiagnosisStatus />} />
          <Route path="/reports/:reportId" element={<ReportView />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
