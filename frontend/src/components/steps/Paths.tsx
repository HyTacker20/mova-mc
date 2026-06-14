import { useState } from 'react'
import { useWizard } from '../../context/WizardContext'
import { api } from '../../api/client'

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
    // Persist path settings on explicit Next
    api.saveConfig({
      source,
      target,
      mods_path: modsPath,
      output: outputPath,
      output_mode: outputMode,
      config_path: state.configPath ?? undefined,
    }).catch(() => {})
    dispatch({ type: 'SET_PATHS', source, target, modsPath, outputPath, outputMode })
    dispatch({ type: 'SET_STEP', step: 3 })
  }

  return (
    <div className="step-card">
      <h2 className="step-title">Paths &amp; Languages</h2>
      <p className="step-subtitle">Configure source and output locations.</p>

      <div className="row">
        <div className="field">
          <label htmlFor="source-lang">Source language</label>
          <select id="source-lang" value={source} onChange={e => setSource(e.target.value)}>
            {COMMON_LANGS.map(([code, name]) => (
              <option key={code} value={code}>{name} ({code})</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="target-lang">Target language</label>
          <select id="target-lang" value={target} onChange={e => setTarget(e.target.value)}>
            {COMMON_LANGS.map(([code, name]) => (
              <option key={code} value={code}>{name} ({code})</option>
            ))}
          </select>
        </div>
      </div>

      <div className="field">
        <label htmlFor="mods-path">Mods directory</label>
        <input
          id="mods-path"
          type="text"
          value={modsPath}
          onChange={e => setModsPath(e.target.value)}
          placeholder="./mods"
        />
        <p className="hint">Absolute or relative path to the folder containing .jar files</p>
      </div>

      <div className="field">
        <label htmlFor="output-path">Output directory</label>
        <input
          id="output-path"
          type="text"
          value={outputPath}
          onChange={e => setOutputPath(e.target.value)}
          placeholder="./translated_mods"
        />
      </div>

      <div className="field">
        <label htmlFor="output-mode">Output mode</label>
        <select id="output-mode" value={outputMode} onChange={e => setOutputMode(e.target.value)}>
          <option value="resourcepack">Resource Pack — build a Minecraft resource pack .zip</option>
          <option value="separate">Separate — write translated JARs to output directory</option>
          <option value="replace">Replace — overwrite original JARs</option>
        </select>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 1 })}>
          ← Back
        </button>
        <button className="btn-primary" onClick={next}>
          Next →
        </button>
      </div>
    </div>
  )
}
