import { Routes, Route, Link } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Funds from './pages/Funds.jsx'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">Fon Analiz</Link>
        <nav>
          <Link to="/">Ana Sayfa</Link>
          <Link to="/fonlar">Fonlar</Link>
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/fonlar" element={<Funds />} />
        </Routes>
      </main>
    </div>
  )
}
