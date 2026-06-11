import { useEffect, useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'
import type { ModInfo } from '../../types'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function Mods() {
  const { state, dispatch } = useWizard()
  const [mods, setMods] = useState<ModInfo[]>(state.mods)
  const [selected, setSelected] = useState<Set<string>>(new Set(state.selectedMods))
  const [loading, setLoading] = useState(state.mods.length === 0)
  const [error, setError] = useState('')

  useEffect(() => {
    if (state.mods.length > 0) return
    setLoading(true)
    api.scanMods(state.modsPath)
      .then(r => {
        setMods(r.mods)
        setSelected(new Set(r.mods.filter(m => m.has_lang_files).map(m => m.name)))
      })
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [])

  function toggleMod(name: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  function selectAll() { setSelected(new Set(mods.map(m => m.name))) }
  function deselectAll() { setSelected(new Set()) }

  function next() {
    if (selected.size === 0) { setError('Select at least one mod'); return }
    setError('')
    const withSelected: ModInfo[] = mods.map(m => ({ ...m, selected: selected.has(m.name) }))
    dispatch({ type: 'SET_MODS', mods: withSelected })
    dispatch({ type: 'SET_STEP', step: 5 })
  }

  return (
    <div className="step-card wide">
      <h2 className="step-title">Select Mods</h2>
      <p className="step-subtitle">
        Scanning <code style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{state.modsPath}</code>
        {' '}— choose which mods to translate.
      </p>

      {loading && <p style={{ color: 'var(--text-muted)' }}>Scanning…</p>}

      {!loading && error && <p className="error-msg">{error}</p>}

      {!loading && !error && mods.length === 0 && (
        <p style={{ color: 'var(--text-muted)' }}>No .jar files found in this directory.</p>
      )}

      {!loading && mods.length > 0 && (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <button className="btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={selectAll}>Select all</button>
            <button className="btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={deselectAll}>Deselect all</button>
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
              {selected.size} / {mods.length} selected
            </span>
          </div>

          <div className="mods-list">
            {mods.map(mod => (
              <label key={mod.name} className={`mod-row ${!mod.has_lang_files ? 'mod-row--no-lang' : ''}`}>
                <input type="checkbox" checked={selected.has(mod.name)} onChange={() => toggleMod(mod.name)} />
                <span className="mod-name">{mod.name}</span>
                <span className="mod-meta">
                  {mod.has_lang_files
                    ? `${mod.lang_file_count} lang file${mod.lang_file_count !== 1 ? 's' : ''}, ~${mod.estimated_entries} entries`
                    : 'no lang files'}
                </span>
                <span className="mod-size">{formatBytes(mod.size_bytes)}</span>
              </label>
            ))}
          </div>
        </>
      )}

      {error && mods.length === 0 && (
        <button className="btn-ghost" style={{ marginTop: 12 }} onClick={() => {
          setError('')
          setLoading(true)
          api.scanMods(state.modsPath)
            .then(r => { setMods(r.mods); setSelected(new Set(r.mods.filter(m => m.has_lang_files).map(m => m.name))) })
            .catch(e => setError(String(e.message ?? e)))
            .finally(() => setLoading(false))
        }}>Retry</button>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 3 })}>← Back</button>
        <button className="btn-primary" onClick={next} disabled={selected.size === 0 || loading}>
          Translate {selected.size > 0 ? `${selected.size} mod${selected.size !== 1 ? 's' : ''}` : ''} →
        </button>
      </div>
    </div>
  )
}
