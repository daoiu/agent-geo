import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NewDiagnosis from './pages/NewDiagnosis';
import DiagnosisStatus from './pages/DiagnosisStatus';
import ReportView from './pages/ReportView';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/diagnosis/new" element={<NewDiagnosis />} />
        <Route path="/diagnosis/status/:taskId" element={<DiagnosisStatus />} />
        <Route path="/reports/:reportId" element={<ReportView />} />
        <Route
          path="/"
          element={
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
              <div className="text-center">
                <h1 className="text-4xl font-bold text-gray-900 mb-4">
                  GEO 诊断 Agent
                </h1>
                <p className="text-gray-600">脚手架就绪 - 等待功能开发</p>
              </div>
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
