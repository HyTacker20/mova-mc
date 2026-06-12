import { useEffect, useRef, useState } from 'react'
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
  const configPathRef = useRef<string | null>(null)
  // Remember the last model selected for each provider so toggling
  // away and back doesn't lose the user's choice.
  const modelCacheRef = useRef<Record<string, string>>({})

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
        configPathRef.current = cfg.config_path
        dispatch({ type: 'SET_CONFIG_PATH', path: cfg.config_path })
        // Provider fields
        if (cfg.provider && cfg.provider !== state.provider) {
          setProvider(cfg.provider)
          dispatch({ type: 'SET_PROVIDER', provider: cfg.provider, model: cfg.model ?? '' })
        }
        if (cfg.model && cfg.model !== state.model) {
          setModel(cfg.model)
        }
        // Seed the model cache so handleProviderChange can restore models
        if (cfg.provider && cfg.model) {
          modelCacheRef.current[cfg.provider] = cfg.model
        }
        // Paths & Advanced fields — sync into wizard state so other steps
        // pick them up without re-fetching.
        dispatch({
          type: 'SET_PATHS',
          source: cfg.source,
          target: cfg.target,
          modsPath: state.modsPath,
          outputPath: cfg.output || state.outputPath,
          outputMode: cfg.output_mode || 'separate',
        })
        dispatch({
          type: 'SET_ADVANCED',
          workers: cfg.workers,
          noCache: cfg.no_cache,
          dryRun: state.dryRun,
          hintLang: cfg.hint_lang ?? '',
          qaEnabled: cfg.qa?.judge ?? state.qaEnabled,
          qaProvider: cfg.qa?.judge_provider ?? '',
          qaModel: cfg.qa?.judge_model ?? '',
          qaThreshold: cfg.qa?.threshold ?? state.qaThreshold,
          qaMaxAttempts: cfg.qa?.max_attempts ?? state.qaMaxAttempts,
        })
      })
      .catch(() => {/* no config yet — use defaults */})
      .finally(() => setConfigLoaded(true))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const info = providers.find(p => p.id === provider)

  function handleProviderChange(value: string) {
    // Cache current model before switching
    if (model) {
      modelCacheRef.current[provider] = model
    }
    setProvider(value)
    // Restore cached model for this provider, or default to empty
    setModel(modelCacheRef.current[value] || '')
  }

  function handleModelChange(value: string) {
    setModel(value)
    // Keep the cache in sync so handleProviderChange picks it up
    modelCacheRef.current[provider] = value
  }

  function next() {
    // Save config only on explicit Next (provider + model only; path is set on Paths step)
    api.saveConfig({
      provider,
      model: model || info?.default_model || undefined,
      config_path: configPathRef.current ?? undefined,
    }).catch(() => {})
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
