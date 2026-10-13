// Risk profili tarayıcıda saklanır (kullanıcı girişi yok). Gizli pencerede ya da depolama
// kapalıyken okuma/yazma hata verebilir; o durumda sayfa çalışır ama profil hatırlanmaz.
const KEY = 'riskProfili'

export function loadProfile() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY))
    return v && v.result && v.answers ? v : null
  } catch {
    return null
  }
}

// result: POST /api/risk-profile yanıtı
export function saveProfile(answers, qualified, result) {
  const value = { answers, qualified, result, savedAt: new Date().toISOString() }
  try {
    localStorage.setItem(KEY, JSON.stringify(value))
  } catch {
    // depolama yoksa profil sadece bu oturumda yaşar
  }
  return value
}

export function clearProfile() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // yok say
  }
}
