import { Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import ToastStack from './components/ToastStack'
import { WorkbenchProvider } from './context/WorkbenchContext'
import DashboardPage from './pages/DashboardPage'
import PhotoPage from './pages/PhotoPage'
import VoicePage from './pages/VoicePage'
import MusicPage from './pages/MusicPage'
import VideoPage from './pages/VideoPage'
import TokenPage from './pages/TokenPage'
import UsagePage from './pages/UsagePage'
import HelpPage from './pages/HelpPage'
import ApiDocsPage from './pages/ApiDocsPage'
import SettingsPage from './pages/SettingsPage'

function NotFoundRedirect() {
  return <Navigate to="/dashboard" replace />
}

export default function App() {
  return (
    <WorkbenchProvider>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="photo" element={<PhotoPage />} />
          <Route path="voice" element={<VoicePage />} />
          <Route path="music" element={<MusicPage />} />
          <Route path="video" element={<VideoPage />} />
          <Route path="token" element={<TokenPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="help" element={<HelpPage />} />
          <Route path="api-docs" element={<ApiDocsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundRedirect />} />
        </Route>
      </Routes>
      <ToastStack />
    </WorkbenchProvider>
  )
}
