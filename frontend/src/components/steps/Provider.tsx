import { useEffect, useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'
import type { ProviderInfo } from '../../types'

export default function Provider() {
  const { state, dispatch } = useWizard()
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState(state.provider)
  const [model, setModel] = useState(state.model)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getProviders()
      .then(r => setProviders(r.providers))
      .catch(() => {/* ignore — use empty list */})
      .finally(() => setLoading(false))
  }, [])

  const info = providers.find(p => p.id === provider)

  function next() {
    dispatch({ type: 'SET_PROVIDER', provider, model: model || info?.default_model || '' })
    dispatch({ type: 'SET_STEP', step: 2 })
  }

  return (
    <div className="step-card">
      <h2 className="step-title">Translation Provider</h2>
      <p className="step-subtitle">Choose the AI or translation service.</p>

      <div className="field">
        <label>Provider</label>
        <select value={provider} onChange={e => { setProvider(e.target.value); setModel('') }}>
          {loading
            ? <option>Loading…</option>
            : providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </div>

      {info && info.models.length > 0 && (
        <div className="field">
          <label>Model</label>
          <select value={model || info.default_model || ''} onChange={e => setModel(e.target.value)}>
            {info.models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      )}

      {info?.requires_key && (
        <div className="field">
          <div style={{ padding: '10px 14px', background: 'var(--surface2)', borderRadius: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            ℹ Requires <code style={{ color: 'var(--warning)', fontFamily: 'var(--mono)' }}>{info.key_env}</code> in your environment or <code style={{ fontFamily: 'var(--mono)' }}>.env</code> file.
          </div>
        </div>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 0 })}>← Back</button>
        <button className="btn-primary" onClick={next}>Next →</button>
      </div>
    </div>
  )
}
