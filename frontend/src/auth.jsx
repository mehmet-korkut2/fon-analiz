// Oturum bilgisi: kullanıcı, kayıtlı risk profili ve favoriler. Oturum belirteci HttpOnly çerezde (JavaScript
// göremez); burada yalnızca GET /api/auth/ben yanıtı tutulur. Sayfalar oturum bilgisi gelince çizilir, böylece
// girişli/girişsiz görünüm arasında gidip gelmez.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  addFavorite, getFavorites, getMe, getMyProfile, postLogin, postLogout, postMyProfile, postRegister, removeFavorite,
} from './api/client'
import { clearSessionProfile, fromServer, loadSessionProfile, saveSessionProfile } from './profileStore'

const AuthContext = createContext(null)

// Girişten sonra: hesapta profil yoksa bu tarayıcıdaki profil hesaba aktarılır, tarayıcıdan silinir
async function loadAccountProfile() {
  let saved = fromServer(await getMyProfile())
  const local = loadSessionProfile()
  if (!saved && local) saved = fromServer(await postMyProfile(local.answers, Boolean(local.qualified)))
  clearSessionProfile()
  return saved
}

export function AuthProvider({ children }) {
  const [ready, setReady] = useState(false)
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [favorites, setFavorites] = useState(() => new Set())
  const [notice, setNotice] = useState(null) // kayıttan sonra gösterilecek bilgi (ör. portföy aktarıldı)

  const enter = useCallback(async (u) => {
    setUser(u)
    const [p, favs] = await Promise.all([loadAccountProfile().catch(() => null), getFavorites().catch(() => [])])
    setProfile(p)
    setFavorites(new Set(favs.map((f) => f.code)))
  }, [])

  const leave = useCallback(() => {
    setUser(null)
    setProfile(loadSessionProfile())
    setFavorites(new Set())
  }, [])

  useEffect(() => {
    let ignore = false
    getMe()
      .then(async (u) => { if (!ignore) { if (u) await enter(u); else leave() } })
      .catch(() => { if (!ignore) leave() }) // backend kapalıysa girişsiz devam
      .finally(() => { if (!ignore) setReady(true) })
    return () => { ignore = true }
  }, [enter, leave])

  const value = useMemo(() => ({
    ready, user, profile, favorites, notice, setNotice,
    async login(email, password) {
      const r = await postLogin({ email, password })
      await enter(r.user)
      return r
    },
    async register(name, email, password) {
      const r = await postRegister({ name, email, password })
      await enter(r.user)
      if (r.migrated_portfolio) setNotice('Kullanıcı girişinden önceki sanal portföyün bu hesaba aktarıldı.')
      return r
    },
    async logout() {
      try {
        await postLogout()
      } finally {
        clearSessionProfile()
        leave()
      }
    },
    // hesap silindi ya da oturum sunucuda kapandı
    forget: leave,
    setUser,
    async saveProfile(answers, qualified, result) {
      const p = user ? fromServer(await postMyProfile(answers, qualified)) : saveSessionProfile(answers, qualified, result)
      setProfile(p)
      return p
    },
    async toggleFavorite(code) {
      const on = favorites.has(code)
      await (on ? removeFavorite(code) : addFavorite(code))
      setFavorites((prev) => {
        const next = new Set(prev)
        if (on) next.delete(code)
        else next.add(code)
        return next
      })
      return !on
    },
  }), [ready, user, profile, favorites, notice, enter, leave])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)
