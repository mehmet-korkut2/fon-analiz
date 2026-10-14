import { lazy, Suspense } from 'react'
import { Routes, Route, NavLink, Link } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Funds from './pages/Funds.jsx'
import Doviz from './pages/Doviz.jsx'
import Rankings from './pages/Rankings.jsx'
import RiskSurvey from './pages/RiskSurvey.jsx'

// Grafik kütüphanesi (Recharts) büyük; sadece grafikli sayfalar açılınca indirilsin
const FundDetail = lazy(() => import('./pages/FundDetail.jsx'))
const Compare = lazy(() => import('./pages/Compare.jsx'))
const Recommendations = lazy(() => import('./pages/Recommendations.jsx'))
const ModelPerformance = lazy(() => import('./pages/ModelPerformance.jsx'))

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">Fon Analiz</Link>
        <nav>
          <NavLink to="/" end>Ana Sayfa</NavLink>
          <NavLink to="/fonlar">Fonlar</NavLink>
          <NavLink to="/siralamalar">Sıralamalar</NavLink>
          <NavLink to="/karsilastir">Karşılaştır</NavLink>
          <NavLink to="/risk-anketi">Risk Anketi</NavLink>
          <NavLink to="/oneriler">Öneriler</NavLink>
          <NavLink to="/model-performansi">Model</NavLink>
          <NavLink to="/doviz">Döviz ve Altın</NavLink>
        </nav>
      </header>
      <main className="main">
        <Suspense fallback={<p className="muted">Yükleniyor...</p>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/fonlar" element={<Funds />} />
            <Route path="/fonlar/:code" element={<FundDetail />} />
            <Route path="/siralamalar" element={<Rankings />} />
            <Route path="/karsilastir" element={<Compare />} />
            <Route path="/risk-anketi" element={<RiskSurvey />} />
            <Route path="/oneriler" element={<Recommendations />} />
            <Route path="/model-performansi" element={<ModelPerformance />} />
            <Route path="/doviz" element={<Doviz />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="footer">
        <p>
          <strong>Yatırım tavsiyesi değildir.</strong> Bu site bir bitirme projesidir; gösterilen veriler, sıralamalar ve
          öneriler bilgilendirme ve eğitim amaçlıdır, SPK lisanslı yatırım danışmanlığı yerine geçmez. Geçmiş performans
          gelecekteki sonuçların göstergesi değildir. Fon verileri TEFAS'tan alınır.
        </p>
      </footer>
    </div>
  )
}
