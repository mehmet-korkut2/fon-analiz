// Girişsiz kullanıcının risk profili yalnızca bu oturumda (sessionStorage) tutulur; kalıcı kayıt için giriş
// gerekir (girişli kullanıcıda profil sunucuda: GET/POST /api/profilim, src/auth.jsx).
// Kullanıcı girişinden önceki sürüm profili localStorage'a yazıyordu: o profil okunur ve ilk girişte hesaba
// aktarılıp tarayıcıdan silinir. Gizli pencerede ya da depolama kapalıyken okuma/yazma hata verebilir.
const KEY = 'riskProfili'

function read(storage) {
  try {
    const v = JSON.parse(storage.getItem(KEY))
    return v && v.result && v.answers ? v : null
  } catch {
    return null
  }
}

// Bu oturumdaki profil; yoksa eski sürümden kalan (localStorage) profil
export function loadSessionProfile() {
  return read(sessionStorage) ?? read(localStorage)
}

export function saveSessionProfile(answers, qualified, result) {
  const value = { answers, qualified, result, savedAt: new Date().toISOString() }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(value))
  } catch {
    // depolama yoksa profil sadece bu sayfada yaşar
  }
  return value
}

export function clearSessionProfile() {
  for (const s of [sessionStorage, localStorage]) {
    try {
      s.removeItem(KEY)
    } catch {
      // yok say
    }
  }
}

// Sunucudaki kayıt -> sayfaların kullandığı biçim
export const fromServer = (p) => (p ? { answers: p.answers, qualified: p.qualified, result: p.result, savedAt: p.saved_at } : null)
