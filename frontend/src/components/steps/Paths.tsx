import { useState } from 'react'
import { useWizard } from '../../context/WizardContext'

const COMMON_LANGS = [
  ['en_US', 'English (US)'], ['uk_UA', 'Ukrainian'], ['pl_PL', 'Polish'],
  ['de_DE', 'German'], ['fr_FR', 'French'], ['es_ES', 'Spanish'],
  ['pt_BR', 'Portuguese (BR)'], ['ru_RU', 'Russian'], ['zh_CN', 'Chinese (CN)'],
  ['zh_TW', 'Chinese (TW)'], ['ja_JP', 'Japanese'], ['ko_KR', 'Korean'],
  ['tr_TR', 'Turkish'], ['cs_CZ', 'Czech'], ['nl_NL', 'Dutch'],
]

export default function Paths() {
  const { state, dispatch } = useWizard()
  const [source, setSource] = useState(state.source)
  const [target, setTarget] = useState(state.target)
  const [modsPath, setModsPath] = useState(state.modsPath)
  const [outputPath, setOutputPath] = useState(state.outputPath)
  const [outputMode, setOutputMode] = useState(state.outputMode)
  const [error, setError] = useState('')

  function next() {
    if (!modsPath.trim()) { setError('Mods path is required'); return }
    setError('')
    dispatch({ type: 'SET_PATHS', source, target, modsPath, outputPath, outputMode })
    dispatch({ type: 'SET_STEP', step: 3 })
  }

  return (
    <div className="step-card">
      <h2 className="step-title">Paths & Languages</h2>
      <p className="step-subtitle">Configure source and output locations.</p>

      <div className="row">
        <div className="field">
          <label>Source language</label>
          <select value={source} onChange={e => setSource(e.target.value)}>
            {COMMON_LANGS.map(([code, name]) => <option key={code} value={code}>{name} ({code})</option>)}
          </select>
        </div>
        <div className="field">
          <label>Target language</label>
          <select value={target} onChange={e => setTarget(e.target.value)}>
            {COMMON_LANGS.map(([code, name]) => <option key={code} value={code}>{name} ({code})</option>)}
          </select>
        </div>
      </div>

      <div className="field">
        <label>Mods directory</label>
        <input type="text" value={modsPath} onChange={e => setModsPath(e.target.value)} placeholder="./mods" />
        <p className="hint">Absolute or relative path to the folder containing .jar files</p>
      </div>

      <div className="field">
        <label>Output directory</label>
        <input type="text" value={outputPath} onChange={e => setOutputPath(e.target.value)} placeholder="./translated_mods" />
      </div>

      <div className="field">
        <label>Output mode</label>
        <select value={outputMode} onChange={e => setOutputMode(e.target.value)}>
          <option value="separate">Separate — write translated JARs to output directory</option>
          <option value="replace">Replace — overwrite original JARs (DANGEROUS)</option>
        </select>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 1 })}>← Back</button>
        <button className="btn-primary" onClick={next}>Next →</button>
      </div>
    </div>
  )
}
