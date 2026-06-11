import { useEffect, useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'
import type { ProviderInfo } from '../../types'

const QA_CUSTOM = '__custom__'

function qaProviders(providers: ProviderInfo[]): ProviderInfo[] {
  return providers.filter(p => p.id !== 'google' && p.models.length > 0)
}

export default function Advanced() {
  const { state, dispatch } = useWizard()
  const [workers, setWorkers] = useState(state.workers)
  const [noCache, setNoCache] = useState(state.noCache)
  const [dryRun, setDryRun] = useState(state.dryRun)
  const [hintLang, setHintLang] = useState(state.hintLang)
  const [qaEnabled, setQaEnabled] = useState(state.qaEnabled)
  const [qaProvider, setQaProvider] = useState(state.qaProvider)
  const [qaModel, setQaModel] = useState(state.qaModel)
  const [qaCustomModel, setQaCustomModel] = useState('')
  const [qaModelIsCustom, setQaModelIsCustom] = useState(false)
  const [qaThreshold, setQaThreshold] = useState(state.qaThreshold)
  const [qaMaxAttempts, setQaMaxAttempts] = useState(state.qaMaxAttempts)
  const [providers, setProviders] = useState<ProviderInfo[]>([])

  useEffect(() => {
    api.getProviders().then(r => setProviders(r.providers)).catch(() => {})
  }, [])

  useEffect(() => {
    setQaEnabled(state.qaEnabled)
    setQaProvider(state.qaProvider)
    setQaModel(state.qaModel)
    setQaThreshold(state.qaThreshold)
    setQaMaxAttempts(state.qaMaxAttempts)
  }, [state.qaEnabled, state.qaProvider, state.qaModel, state.qaThreshold, state.qaMaxAttempts])

  const llmProviders = qaProviders(providers)
  const qaInfo = llmProviders.find(p => p.id === qaProvider)
  const resolvedQaModel = qaModelIsCustom
    ? qaCustomModel
    : (qaModel || qaInfo?.default_model || '')

  useEffect(() => {
    if (!qaProvider || !qaInfo) return
    const known = qaInfo.models
    if (qaModel && known.includes(qaModel)) {
      setQaModelIsCustom(false)
      return
    }
    if (qaModel && !known.includes(qaModel)) {
      setQaModelIsCustom(true)
      setQaCustomModel(qaModel)
      return
    }
    if (!qaModel && qaInfo.default_model) {
      setQaModel(qaInfo.default_model)
      setQaModelIsCustom(false)
    }
  }, [qaProvider, qaInfo, qaModel])

  function handleQaProviderChange(value: string) {
    setQaProvider(value)
    setQaModelIsCustom(false)
    setQaCustomModel('')
    if (!value) {
      setQaModel('')
      return
    }
    const info = llmProviders.find(p => p.id === value)
    setQaModel(info?.default_model ?? '')
  }

  function handleQaModelChange(value: string) {
    if (value === QA_CUSTOM) {
      setQaModelIsCustom(true)
      setQaCustomModel(qaModel || qaInfo?.default_model || '')
      return
    }
    setQaModelIsCustom(false)
    setQaCustomModel('')
    setQaModel(value)
  }

  function next() {
    const judgeModel = qaProvider ? (resolvedQaModel || null) : null
    api.saveConfig({
      workers,
      no_cache: noCache,
      hint_lang: hintLang || undefined,
      qa: {
        judge: qaEnabled,
        judge_provider: qaProvider || null,
        judge_model: judgeModel,
        threshold: qaThreshold,
        max_attempts: qaMaxAttempts,
      },
      config_path: state.configPath ?? undefined,
    }).catch(() => {})
    dispatch({
      type: 'SET_ADVANCED',
      workers,
      noCache,
      dryRun,
      hintLang,
      qaEnabled,
      qaProvider,
      qaModel: judgeModel ?? '',
      qaThreshold,
      qaMaxAttempts,
    })
    dispatch({ type: 'SET_STEP', step: 4 })
  }

  const translatorModel = state.model || '(default)'

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
              <select
                id="qa-provider"
                value={qaProvider}
                onChange={e => handleQaProviderChange(e.target.value)}
              >
                <option value="">Same as translator</option>
                {llmProviders.map(p => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>
            {qaProvider && qaInfo && (
              <div className="field">
                <label htmlFor="qa-model">QA model</label>
                <select
                  id="qa-model"
                  value={qaModelIsCustom ? QA_CUSTOM : (qaModel || qaInfo.default_model || '')}
                  onChange={e => handleQaModelChange(e.target.value)}
                >
                  {qaInfo.models.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  <option value={QA_CUSTOM}>Custom…</option>
                </select>
                {qaModelIsCustom && (
                  <input
                    id="qa-model-custom"
                    type="text"
                    value={qaCustomModel}
                    onChange={e => setQaCustomModel(e.target.value)}
                    placeholder="Type custom model name"
                    style={{ marginTop: 8 }}
                  />
                )}
                <p className="hint">Judge model for quality review (separate from translation model)</p>
              </div>
            )}
          </div>
          {!qaProvider && (
            <p className="hint" style={{ marginBottom: 14 }}>
              Using: <strong>{state.provider}</strong> / <strong>{translatorModel}</strong> (from translator settings)
            </p>
          )}
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
