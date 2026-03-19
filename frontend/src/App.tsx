import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import InstallationPage from './pages/InstallationPage';

// Placeholder Dashboard for now
const Dashboard = () => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 font-ibm-plex text-center px-4" dir="rtl">
    <div className="bg-white p-12 rounded-2xl shadow-xl space-y-6">
      <h1 className="text-4xl font-bold text-thaqib-primary">لوحة التحكم</h1>
      <p className="text-gray-600 text-lg">مرحباً بك في نظام ثاقب. سيتم إضافة الوظائف هنا قريباً.</p>
      <button 
        onClick={() => { localStorage.clear(); window.location.href = '/login'; }}
        className="px-8 py-3 bg-red-600 text-white rounded-lg font-bold hover:bg-red-700 transition-all active:scale-95"
      >
        تسجيل الخروج
      </button>
    </div>
  </div>
);

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/setup" element={<InstallationPage />} />

          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<Dashboard />} />
          </Route>

          {/* Root Redirects */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
