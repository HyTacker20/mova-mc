import { useWizard } from '../../context/WizardContext'

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

export default function Summary() {
  const { state, dispatch } = useWizard()
  const { stats, error, jobStatus } = state
  const success = jobStatus === 'done' && stats !== null

  return (
    <div className="step-card wide">
      <h2 className="step-title">{success ? 'Translation complete' : 'Translation finished'}</h2>

      {error && <p className="error-msg" style={{ marginBottom: 16 }}>{error}</p>}

      {success && stats && (
        <>
          <div className="summary-grid">
            <div className="summary-stat">
              <span className="summary-stat-value">{stats.translated_mods}</span>
              <span className="summary-stat-label">mods translated</span>
            </div>
            <div className="summary-stat">
              <span className="summary-stat-value">{stats.translated_entries}</span>
              <span className="summary-stat-label">entries translated</span>
            </div>
            <div className="summary-stat">
              <span className="summary-stat-value">{stats.failed_entries}</span>
              <span className="summary-stat-label">failed</span>
            </div>
            <div className="summary-stat">
              <span className="summary-stat-value">{formatDuration(stats.duration_seconds)}</span>
              <span className="summary-stat-label">duration</span>
            </div>
          </div>

          <p className="step-subtitle" style={{ marginTop: 20, marginBottom: 12 }}>
            {stats.provider} · {stats.source_lang} → {stats.target_lang}
            {state.dryRun ? ' · dry run (no files written)' : ''}
          </p>

          {stats.mods.length > 0 && (
            <div className="summary-table-wrap">
              <table className="summary-table">
                <thead>
                  <tr>
                    <th>Mod</th>
                    <th>Entries</th>
                    <th>Failed</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.mods.map(mod => (
                    <tr key={mod.name}>
                      <td>{mod.name}</td>
                      <td>{mod.translated_entries} / {mod.total_entries}</td>
                      <td>{mod.failed_entries}</td>
                      <td>{mod.skipped ? 'skipped' : mod.failed_entries > 0 ? 'partial' : 'ok'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!state.dryRun && (
            <p className="hint" style={{ marginTop: 16 }}>
              Output: {state.outputMode === 'replace' ? state.modsPath : state.outputPath}
            </p>
          )}
        </>
      )}

      {!success && !error && (
        <p style={{ color: 'var(--text-muted)' }}>No results to display.</p>
      )}

      <div className="step-actions">
        <button className="btn-ghost" onClick={() => dispatch({ type: 'SET_STEP', step: 4 })}>
          ← Back to mods
        </button>
        <button
          className="btn-primary"
          onClick={() => {
            dispatch({ type: 'RESET' })
            dispatch({ type: 'SET_STEP', step: 0 })
          }}
        >
          New translation
        </button>
      </div>
    </div>
  )
}
