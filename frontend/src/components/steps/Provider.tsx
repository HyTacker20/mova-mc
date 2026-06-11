import { useCallback, useEffect, useRef, useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'
import type { ConfigResponse, ProviderInfo } from '../../types'

export default function Provider() {
  const { state, dispatch } = useWizard()
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState(state.provider)
  const [model, setModel] = useState(state.model)
  const [loading, setLoading] = useState(true)
  const [configLoaded, setConfigLoaded] = useState(false)
  const [loadError, setLoadError] = useState('')
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const providerRef = useRef(provider)
  const modelRef = useRef(model)
  providerRef.current = provider
  modelRef.current = model

  // Load provider catalog
  useEffect(() => {
    api.getProviders()
      .then(r => setProviders(r.providers))
      .catch(() => setLoadError('Could not load providers. Check your backend connection.'))
      .finally(() => setLoading(false))
  }, [])

  // Load saved config from movamc.toml on mount
  useEffect(() => {
    if (configLoaded) return
    api.getConfig(state.modsPath)
      .then((cfg: ConfigResponse) => {
        if (cfg.provider && cfg.provider !== state.provider) {
          setProvider(cfg.provider)
          dispatch({ type: 'SET_PROVIDER', provider: cfg.provider, model: cfg.model ?? '' })
        }
        if (cfg.model && cfg.model !== state.model) {
          setModel(cfg.model)
        }
      })
      .catch(() => {/* no config yet — use defaults */})
      .finally(() => setConfigLoaded(true))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced auto-save to movamc.toml
  const scheduleSave = useCallback(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      api.saveConfig({
        provider: providerRef.current,
        model: modelRef.current || undefined,
        mods_path: state.modsPath,
      }).catch(() => {/* silent — config save is best-effort */})
    }, 400)
  }, [state.modsPath])

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  const info = providers.find(p => p.id === provider)

  function handleProviderChange(value: string) {
    setProvider(value)
    setModel('')
    // Save immediately on provider change
    api.saveConfig({
      provider: value,
      model: undefined,
      mods_path: state.modsPath,
    }).catch(() => {})
  }

  function handleModelChange(value: string) {
    setModel(value)
    scheduleSave()
  }

  function next() {
    dispatch({ type: 'SET_PROVIDER', provider, model: model || info?.default_model || '' })
    dispatch({ type: 'SET_STEP', step: 2 })
  }

  if (loading) {
    return (
      <div className="step-card">
        <div className="skeleton skeleton-line" style={{ width: '40%', height: 22, marginBottom: 16 }} />
        <div className="skeleton skeleton-line" style={{ width: '60%', height: 16, marginBottom: 24 }} />
        <div className="skeleton skeleton-select" />
        <div className="skeleton skeleton-select" />
      </div>
    )
  }

  return (
    <div className="step-card">
      <h2 className="step-title">Translation Provider</h2>
      <p className="step-subtitle">Choose the AI or translation service.</p>

      {loadError && <p className="error-msg" style={{ marginBottom: 14 }}>{loadError}</p>}

      <div className="field">
        <label htmlFor="provider-select">Provider</label>
        <select id="provider-select" value={provider} onChange={e => handleProviderChange(e.target.value)}>
          {providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </div>

      {info && info.models.length > 0 && (
        <div className="field">
          <label htmlFor="model-select">Model</label>
          <select id="model-select" value={model || info.default_model || ''} onChange={e => handleModelChange(e.target.value)}>
            {info.models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      )}

      {info?.requires_key && (
        <div className="info-box">
          Requires <code style={{ color: 'var(--warning)' }}>{info.key_env}</code> in your
          environment or <code>.env</code> file.
        </div>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 0 })}>
          ← Back
        </button>
        <button className="btn-primary" onClick={next}>
          Next →
        </button>
      </div>
    </div>
  )
}
