import { useEffect, useState } from 'react'
import { getFunds } from '../api/client'
import { useDebounced } from '../hooks'

// Fon arama kutusu ve öneri listesi (Karşılaştır, Sanal portföy). params: getFunds'a ek süzgeçler
export default function FundPicker({ selected = [], onAdd, label = 'Fon ekle', placeholder = 'Fon kodu veya adı yazıp ekle...', params, id }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const q = useDebounced(query.trim())
  const extra = JSON.stringify(params ?? {})

  useEffect(() => {
    if (!q) { setResults([]); return }
    let ignore = false
    getFunds({ q, page_size: 8, sort: 'ret_1y', ...JSON.parse(extra) })
      .then((d) => { if (!ignore) setResults(d.sample ? [] : d.items) })
      .catch(() => { if (!ignore) setResults([]) })
    return () => { ignore = true }
  }, [q, extra])

  const add = (code) => { onAdd(code); setQuery(''); setResults([]) }

  return (
    <div className="picker">
      <label className="search">
        <span className="sr-only">{label}</span>
        <input
          id={id} type="search" placeholder={placeholder} value={query} autoComplete="off"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && results[0] && !selected.includes(results[0].code)) { e.preventDefault(); add(results[0].code) }
            if (e.key === 'Escape') setResults([])
          }}
        />
      </label>
      {results.length > 0 && (
        <ul className="picker-results">
          {results.map((f) => {
            const taken = selected.includes(f.code)
            return (
              <li key={f.code}>
                <button type="button" disabled={taken} onClick={() => add(f.code)}>
                  <strong className="num">{f.code}</strong>
                  <span className="picker-name">{f.name}</span>
                  {taken && <span className="muted small">seçili</span>}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
