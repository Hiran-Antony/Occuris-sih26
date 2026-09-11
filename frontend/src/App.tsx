import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import RegionalMonitoring from './pages/RegionalMonitoring';
import MaritimeMemory from './pages/MaritimeMemory';
import { ForensicInvestigation } from './pages/ForensicInvestigation';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/monitoring" replace />} />
            <Route path="/monitoring" element={<RegionalMonitoring />} />
            <Route path="/memory"     element={<MaritimeMemory />} />
            <Route path="/forensics"  element={<ForensicInvestigation />} />
            <Route path="*"           element={<Navigate to="/monitoring" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

