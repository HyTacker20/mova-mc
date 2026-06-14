import { useEffect, useMemo, useRef, useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'
import { friendlyError } from '../../utils/errors'
import type { ModInfo } from '../../types'

type SortMode = 'pack' | 'name-asc' | 'name-desc' | 'entries-desc' | 'entries-asc' | 'size-desc' | 'size-asc'

const SORT_LABELS: Record<SortMode, string> = {
  'pack': 'Pack first',
  'name-asc': 'Name A–Z',
  'name-desc': 'Name Z–A',
  'entries-desc': 'Entries ↓',
  'entries-asc': 'Entries ↑',
  'size-desc': 'Size ↓',
  'size-asc': 'Size ↑',
}

const SORT_FN: Record<SortMode, (a: ModInfo, b: ModInfo) => number> = {
  'pack': (a, b) => {
    if (a.in_resource_pack !== b.in_resource_pack) return a.in_resource_pack ? -1 : 1
    return a.name.localeCompare(b.name)
  },
  'name-asc': (a, b) => a.name.localeCompare(b.name),
  'name-desc': (a, b) => b.name.localeCompare(a.name),
  'entries-desc': (a, b) => b.estimated_entries - a.estimated_entries,
  'entries-asc': (a, b) => a.estimated_entries - b.estimated_entries,
  'size-desc': (a, b) => b.size_bytes - a.size_bytes,
  'size-asc': (a, b) => a.size_bytes - b.size_bytes,
}

function SortDropdown({ value, onChange }: { value: SortMode; onChange: (v: SortMode) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div className="sort-dropdown" ref={ref}>
      <button className="sort-dropdown-trigger" onClick={() => setOpen(!open)}>
        {SORT_LABELS[value]}
        <span className={`sort-dropdown-arrow ${open ? 'sort-dropdown-arrow--open' : ''}`}>▾</span>
      </button>
      {open && (
        <div className="sort-dropdown-menu">
          {Object.entries(SORT_LABELS).map(([k, label]) => (
            <button
              key={k}
              className={`sort-dropdown-item ${k === value ? 'sort-dropdown-item--active' : ''}`}
              onClick={() => { onChange(k as SortMode); setOpen(false) }}
            >
              {k === value && <span className="sort-dropdown-check">✓</span>}
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

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
  const [showNoLang, setShowNoLang] = useState(false)
  const [sortBy, setSortBy] = useState<SortMode>('pack')

  const modsWithLang = useMemo(
    () => [...mods].filter(m => m.has_lang_files).sort(SORT_FN[sortBy]),
    [mods, sortBy],
  )
  const modsWithoutLang = mods.filter(m => !m.has_lang_files)
  const inPackCount = mods.filter(m => m.in_resource_pack).length
  const hasExistingPack = inPackCount > 0

  const selectedTotals = useMemo(() => {
    let entries = 0
    let size = 0
    for (const m of modsWithLang) {
      if (selected.has(m.name)) {
        entries += m.estimated_entries
        size += m.size_bytes
      }
    }
    return { entries, size }
  }, [modsWithLang, selected])

  function doScan() {
    setLoading(true)
    setError('')
    api.scanMods(state.modsPath, state.source, state.target, state.outputPath, state.outputMode)
      .then(r => {
        setMods(r.mods)
        if (r.mods.some(m => m.in_resource_pack)) {
          const auto = new Set(
            r.mods
              .filter(m => m.in_resource_pack || m.has_lang_files)
              .map(m => m.name),
          )
          setSelected(auto)
        } else {
          setSelected(new Set(r.mods.filter(m => m.has_lang_files).map(m => m.name)))
        }
      })
      .catch(e => setError(friendlyError(String(e.message ?? e))))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (state.mods.length > 0) return
    doScan()
  }, [])

  // Ctrl+A / Cmd+A to select all
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        // Only intercept when no input/textarea is focused
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        e.preventDefault()
        selectAll()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [modsWithLang])

  function toggleMod(name: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  function selectAll() { setSelected(new Set(modsWithLang.map(m => m.name))) }
  function deselectAll() { setSelected(new Set()) }

  function next() {
    if (selected.size === 0) { setError('Select at least one mod'); return }
    setError('')
    const withSelected: ModInfo[] = mods.map(m => ({ ...m, selected: selected.has(m.name) }))
    dispatch({ type: 'SET_MODS', mods: withSelected })
    dispatch({ type: 'SET_STEP', step: 5 })
  }

  function renderModRow(mod: ModInfo) {
    const isSelected = selected.has(mod.name)
    const isDisabled = !mod.has_lang_files
    return (
      <label
        key={mod.name}
        className={`mod-row ${isDisabled ? 'mod-row--no-lang' : ''} ${mod.in_resource_pack ? 'mod-row--in-pack' : ''}`}
        role="option"
        aria-selected={isDisabled ? undefined : isSelected}
        aria-disabled={isDisabled || undefined}
        tabIndex={isDisabled ? -1 : 0}
        onKeyDown={(e) => {
          if (isDisabled) return
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            toggleMod(mod.name)
          }
        }}
      >
        <input
          type="checkbox"
          checked={selected.has(mod.name)}
          disabled={!mod.has_lang_files}
          onChange={() => toggleMod(mod.name)}
        />
        <span className="mod-name">{mod.name}</span>
        {mod.has_lang_files ? (
          <>
            <span className="mod-meta">
              ~{mod.estimated_entries} entries
            </span>
            <span className="mod-size">{formatBytes(mod.size_bytes)}</span>
            {mod.in_resource_pack && (
                          <span
                            className="mod-badge mod-badge--in-pack"
                            data-tooltip={`Already in resource pack (${inPackCount} mod${inPackCount !== 1 ? 's' : ''} total). Translating will rebuild the pack.`}
                            onMouseEnter={e => {
                              const el = e.currentTarget as HTMLElement
                              const tip = el.querySelector('.mod-tooltip') as HTMLElement
                              if (!tip) return
                              const rect = el.getBoundingClientRect()
                              tip.style.left = `${rect.left + rect.width / 2}px`
                              tip.style.top = `${rect.top - 8}px`
                              tip.style.display = 'block'
                            }}
                            onMouseLeave={e => {
                              const tip = (e.currentTarget as HTMLElement).querySelector('.mod-tooltip') as HTMLElement
                              if (tip) tip.style.display = 'none'
                            }}
                          >
                            ✓ in pack
                            <span className="mod-badge-hint">?</span>
                            <span className="mod-tooltip">{`Already in resource pack (${inPackCount} mod${inPackCount !== 1 ? 's' : ''} total). Translating will rebuild the pack.`}</span>
                          </span>
                        )}
          </>
        ) : (
          <span className="mod-badge mod-badge--no-lang" title="No language files to translate">no lang</span>
        )}
      </label>
    )
  }

  return (
    <div className="step-card wide step-card--fill">
      <h2 className="step-title">Select Mods</h2>
      <p className="step-subtitle">
        Scanning <code>{state.modsPath}</code> — choose which mods to translate.
      </p>

      {loading && (
        <div>
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-line" />
        </div>
      )}

      {!loading && error && <p className="error-msg">{error}</p>}

      {!loading && !error && mods.length === 0 && (
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.5 }} aria-hidden="true">📂</div>
          <p style={{ color: 'var(--text-muted)', marginBottom: 16 }}>No .jar files found in this directory.</p>
          <button
            className="btn-ghost btn-sm"
            onClick={() => dispatch({ type: 'SET_STEP', step: 2 })}
          >
            ← Choose a different folder
          </button>
        </div>
      )}

      {!loading && mods.length > 0 && (
        <>
          <div className="mods-toolbar">
            <button className="btn-ghost btn-sm" onClick={selectAll}>Select all</button>
            <button className="btn-ghost btn-sm" onClick={deselectAll}>Deselect all</button>
            <span className="mods-separator" />
            <SortDropdown value={sortBy} onChange={setSortBy} />
            <span className="mods-counter">
              {selected.size} / {modsWithLang.length} selected
            </span>
          </div>

          <div className="mods-list" role="listbox" aria-multiselectable="true">
            {modsWithLang.map(renderModRow)}
          </div>

          {selected.size > 0 && (
            <p className="mods-summary">
              ~{selectedTotals.entries} entries · {formatBytes(selectedTotals.size)}
            </p>
          )}

          {modsWithoutLang.length > 0 && (
            <div className="mods-no-lang-section">
              <button
                className="mods-no-lang-toggle"
                onClick={() => setShowNoLang(prev => !prev)}
              >
                <span className={`mods-no-lang-chevron ${showNoLang ? 'mods-no-lang-chevron--open' : ''}`}>▸</span>
                {modsWithoutLang.length} mod{modsWithoutLang.length !== 1 ? 's' : ''} without language files
              </button>
              {showNoLang && (
                <div className="mods-no-lang-list">
                  {modsWithoutLang.map(mod => (
                    <span key={mod.name} className="mods-no-lang-name">{mod.name}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {error && mods.length === 0 && (
        <button
          className="btn-ghost"
          style={{ marginTop: 12 }}
          onClick={doScan}
        >
          Retry
        </button>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 3 })}>
          ← Back
        </button>
        <button
          className="btn-primary"
          onClick={next}
          disabled={selected.size === 0 || loading}
        >
          Translate{selected.size > 0 ? ` ${selected.size} mod${selected.size !== 1 ? 's' : ''}` : ''} →
        </button>
      </div>
    </div>
  )
}
