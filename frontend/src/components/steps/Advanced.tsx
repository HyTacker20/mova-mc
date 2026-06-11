import { useEffect, useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'
import type { ProviderInfo } from '../../types'

export default function Advanced() {
  const { state, dispatch } = useWizard()
  const [workers, setWorkers] = useState(state.workers)
  const [noCache, setNoCache] = useState(state.noCache)
  const [dryRun, setDryRun] = useState(state.dryRun)
  const [hintLang, setHintLang] = useState(state.hintLang)
  const [qaEnabled, setQaEnabled] = useState(state.qaEnabled)
  const [qaProvider, setQaProvider] = useState(state.qaProvider || 'openai')
  const [qaModel, setQaModel] = useState(state.qaModel)
  const [qaThreshold, setQaThreshold] = useState(state.qaThreshold)
  const [qaMaxAttempts, setQaMaxAttempts] = useState(state.qaMaxAttempts)
  const [providers, setProviders] = useState<ProviderInfo[]>([])

  useEffect(() => {
    api.getProviders().then(r => setProviders(r.providers)).catch(() => {})
  }, [])

  function next() {
    dispatch({
      type: 'SET_ADVANCED',
      workers,
      noCache,
      dryRun,
      hintLang,
      qaEnabled,
      qaProvider,
      qaModel,
      qaThreshold,
      qaMaxAttempts,
    })
    dispatch({ type: 'SET_STEP', step: 4 })
  }

  return (
    <div className="step-card">
      <h2 className="step-title">Advanced Settings</h2>
      <p className="step-subtitle">Tune performance and quality assurance.</p>

      <div className="row">
        <div className="field" style={{ flex: '0 0 160px' }}>
          <label htmlFor="workers">Workers</label>
          <input
            id="workers"
            type="number"
            min={1}
            max={32}
            value={workers}
            onChange={e => setWorkers(Math.max(1, Math.min(32, parseInt(e.target.value) || 1)))}
          />
          <p className="hint">Parallel translation threads</p>
        </div>
        <div className="field">
          <label htmlFor="hint-lang">Hint language code</label>
          <input
            id="hint-lang"
            type="text"
            value={hintLang}
            onChange={e => setHintLang(e.target.value)}
            placeholder="e.g. uk (optional)"
          />
          <p className="hint">Extra language context passed to LLM providers</p>
        </div>
      </div>

      <div className="checkboxes">
        <label className="check-row">
          <input type="checkbox" checked={noCache} onChange={e => setNoCache(e.target.checked)} />
          <span>Skip cache <small>(always re-translate)</small></span>
        </label>
        <label className="check-row">
          <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />
          <span>Dry run <small>(scan and count entries without translating)</small></span>
        </label>
      </div>

      <div className="section-divider" />

      <label className="check-row" style={{ marginBottom: 14 }}>
        <input type="checkbox" checked={qaEnabled} onChange={e => setQaEnabled(e.target.checked)} />
        <span style={{ fontWeight: 600 }}>Enable LLM-as-judge QA</span>
      </label>

      {qaEnabled && (
        <div className="qa-section">
          <div className="row">
            <div className="field">
              <label htmlFor="qa-provider">QA provider</label>
              <select id="qa-provider" value={qaProvider} onChange={e => setQaProvider(e.target.value)}>
                {providers.filter(p => p.models.length > 0).map(p => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="qa-model">QA model</label>
              <input
                id="qa-model"
                type="text"
                value={qaModel}
                onChange={e => setQaModel(e.target.value)}
                placeholder="e.g. gpt-4o-mini"
              />
            </div>
          </div>
          <div className="row">
            <div className="field" style={{ flex: '0 0 160px' }}>
              <label htmlFor="qa-threshold">Threshold (1–5)</label>
              <input
                id="qa-threshold"
                type="number"
                min={1}
                max={5}
                value={qaThreshold}
                onChange={e => setQaThreshold(Math.max(1, Math.min(5, parseInt(e.target.value) || 3)))}
              />
            </div>
            <div className="field" style={{ flex: '0 0 160px' }}>
              <label htmlFor="qa-max-attempts">Max attempts</label>
              <input
                id="qa-max-attempts"
                type="number"
                min={1}
                max={5}
                value={qaMaxAttempts}
                onChange={e => setQaMaxAttempts(Math.max(1, Math.min(5, parseInt(e.target.value) || 2)))}
              />
            </div>
          </div>
        </div>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 2 })}>
          ← Back
        </button>
        <button className="btn-primary" onClick={next}>
          Next →
        </button>
      </div>
    </div>
  )
}
