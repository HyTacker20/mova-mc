import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { api } from '../../api/client'
import { useWizard } from '../../context/WizardContext'
import type { JobRequest, QaLiveEntry, WizardState } from '../../types'
import {
  formatQaKey,
  formatTextChangePreview,
  formatTextPreview,
  groupQaEntries,
  summarizeCorrectionFailures,
  type QaEntryGroup,
  type QaPanelItem,
} from '../../utils/qaLive'

function buildJobRequest(state: WizardState): JobRequest {
  return {
    source: state.source,
    target: state.target,
    provider: state.provider,
    model: state.model || null,
    workers: state.workers,
    path: state.modsPath,
    output: state.outputPath,
    output_mode: state.outputMode,
    no_cache: state.noCache,
    dry_run: state.dryRun,
    hint_lang: state.hintLang || null,
    glossary_path: null,
    chunk_mode: 'auto',
    selected_mods: state.selectedMods,
    qa: {
      enabled: state.qaEnabled,
      provider: state.qaProvider || null,
      model: state.qaModel || null,
      threshold: state.qaThreshold,
      max_attempts: state.qaMaxAttempts,
      chunk_size: state.qaChunkSize,
      judge_workers: state.qaJudgeWorkers,
      corrector_model: state.qaCorrectorModel || null,
    },
    rate_limit: {
      rpm: null,
      burst: null,
      judge_rpm: null,
      judge_burst: null,
    },
  }
}

function pct(done: number, total: number): number {
  if (total <= 0) return 0
  return Math.min(100, Math.round((done / total) * 100))
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}m ${s}s`
}

function estimateEtaSeconds(done: number, total: number, elapsedS: number): number | null {
  if (done <= 0 || total <= done || elapsedS <= 1) return null
  const rate = done / elapsedS
  if (rate <= 0) return null
  return (total - done) / rate
}

function renderQaMeta(entry: QaLiveEntry, style: CSSProperties) {
  if (entry.kind === 'summary') {
    return (
      <div key={entry.uid} className="qa-row qa-row--meta" style={style}>
        <span className="qa-meta-text">
          ← batch · {entry.flagged}/{entry.total} flagged, {entry.corrected} corrected ({entry.elapsed.toFixed(1)}s)
        </span>
      </div>
    )
  }
  if (entry.kind === 'done') {
    return (
      <div key={entry.uid} className="qa-row qa-row--done" style={style}>
        <span className="qa-done-text">✓ QA done: {entry.flagged} flagged, {entry.corrected} corrected</span>
      </div>
    )
  }
  if (entry.kind === 'status') {
    return (
      <div key={entry.uid} className="qa-row qa-row--status" style={style}>
        <span className="qa-status-text">{entry.message}</span>
      </div>
    )
  }
  if (entry.kind === 'error') {
    return (
      <div key={entry.uid} className="qa-row qa-row--error" style={style}>
        <span className="qa-error-text">✗ {entry.message}</span>
      </div>
    )
  }
  if (entry.kind === 'warning') {
    return (
      <div key={entry.uid} className="qa-row qa-row--warning" style={style}>
        <span className="qa-key" title={entry.key}>{formatQaKey(entry.key)}</span>
        <span className="qa-badge">⚡ {entry.message}</span>
      </div>
    )
  }
  return null
}

function renderQaGroup(group: QaEntryGroup, style: CSSProperties) {
  const failure = summarizeCorrectionFailures(group)
  const issueBadge = group.fix?.issue || group.flag?.issue || null

  const whyText = group.fix?.why || group.flag?.why

  return (
    <div key={group.key} className="qa-card" style={style}>
      <div className="qa-card-header">
        <span className="qa-card-key" title={group.key}>{group.displayKey}</span>
        {group.flag && !group.fix && (
          <span className="qa-badge">⚠ {group.flag.issue || 'flagged'}</span>
        )}
      </div>
      <div className="qa-card-body">
        {group.source && (
          <div className="qa-card-row">
            <span className="qa-label">src:</span>
            <span className="qa-text-dim">{formatTextPreview(group.source)}</span>
          </div>
        )}
        {group.fix && (
          <>
            <div className="qa-card-row">
              <span className="qa-label">was:</span>
              <span className="qa-text-warn">{formatTextPreview(group.fix.original)}</span>
            </div>
            <div className="qa-card-row">
              <span className="qa-label">now:</span>
              <span className="qa-text-fix">{formatTextPreview(group.fix.fixed)}</span>
            </div>
            {issueBadge && <span className="qa-badge qa-badge--inline">{issueBadge}</span>}
          </>
        )}
        {group.flag && !group.fix && group.flag.translated && (
          <div className="qa-card-row">
            <span className="qa-label">tgt:</span>
            <span className="qa-text-warn">{formatTextPreview(group.flag.translated)}</span>
          </div>
        )}
        {whyText && (
          <div className="qa-card-row qa-card-why">
            <span className="qa-label">why:</span>
            <span className="qa-text-why">{whyText}</span>
          </div>
        )}
        {failure && !group.fix && (
          <div className="qa-card-failure">{failure}</div>
        )}
        {group.notes.length > 0 && (
          <div className="qa-card-notes">
            {group.notes.map((note, i) => (
              <div key={i} className="qa-card-note">↪ {note}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function renderQaPanelItem(item: QaPanelItem, index: number, total: number) {
  const delayMs = (total - 1 - index) * 25
  const style = { animationDelay: `${delayMs}ms` }
  if (item.type === 'meta') {
    return renderQaMeta(item.entry, style)
  }
  return renderQaGroup(item.group, style)
}

export default function TranslationRun() {
  const { state, dispatch } = useWizard()
  const { progress, jobStatus } = state
  const [startError, setStartError] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const [elapsedS, setElapsedS] = useState(0)
  const [showAllBatches, setShowAllBatches] = useState(false)
  const startedRef = useRef(false)
  const esRef = useRef<EventSource | null>(null)
  const stateRef = useRef(state)
  const panelRef = useRef<HTMLDivElement>(null)
  const qaPanelRef = useRef<HTMLDivElement>(null)
  const jobStartRef = useRef<number | null>(null)
  stateRef.current = state

  useEffect(() => {
    if (jobStatus !== 'running') return
    if (jobStartRef.current === null) {
      jobStartRef.current = Date.now()
    }
    const id = window.setInterval(() => {
      if (jobStartRef.current !== null) {
        setElapsedS((Date.now() - jobStartRef.current) / 1000)
      }
    }, 1000)
    return () => window.clearInterval(id)
  }, [jobStatus])

  useEffect(() => {
    const panel = panelRef.current
    if (!panel) return
    panel.scrollTop = panel.scrollHeight
  }, [progress.translations.length])

  useEffect(() => {
    const panel = qaPanelRef.current
    if (!panel) return
    panel.scrollTop = panel.scrollHeight
  }, [progress.qaEntries.length])

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true

    let cancelled = false

    async function finalize(jobId: string) {
      try {
        const job = await api.getJob(jobId)
        if (cancelled) return
        if (job.status === 'done' && job.stats) {
          dispatch({ type: 'JOB_DONE', stats: job.stats })
          dispatch({ type: 'SET_STEP', step: 6 })
          return
        }
        if (job.status === 'cancelled') {
          dispatch({ type: 'JOB_ERROR', error: 'Translation cancelled' })
          return
        }
        dispatch({ type: 'JOB_ERROR', error: job.error ?? `Job ended with status: ${job.status}` })
      } catch (err) {
        if (!cancelled) {
          dispatch({ type: 'JOB_ERROR', error: String((err as Error).message ?? err) })
        }
      }
    }

    async function start() {
      try {
        const created = await api.createJob(buildJobRequest(stateRef.current))
        if (cancelled) return

        dispatch({ type: 'JOB_STARTED', jobId: created.job_id })

        const es = new EventSource(`/api/jobs/${created.job_id}/events`)
        esRef.current = es

        es.onmessage = (ev) => {
          try {
            const frame = JSON.parse(ev.data) as { event: string; data: Record<string, unknown> }
            dispatch({ type: 'PROGRESS', event: frame.event, data: frame.data })
          } catch {
            /* ignore malformed frames */
          }
        }

        es.onerror = () => {
          es.close()
          esRef.current = null
          void finalize(created.job_id)
        }
      } catch (err) {
        if (!cancelled) {
          const msg = String((err as Error).message ?? err)
          setStartError(msg)
          dispatch({ type: 'JOB_ERROR', error: msg })
        }
      }
    }

    void start()

    return () => {
      cancelled = true
      esRef.current?.close()
      esRef.current = null
    }
  }, [dispatch])

  async function handleCancel() {
    if (!state.jobId || cancelling) return
    setCancelling(true)
    try {
      await api.cancelJob(state.jobId)
    } catch (err) {
      setStartError(String((err as Error).message ?? err))
    } finally {
      setCancelling(false)
    }
  }

  const modsDone = progress.fractionalMods ?? progress.completedMods
  const modsPct = pct(modsDone, progress.totalMods)
  const entriesPct = pct(progress.completedEntries, progress.totalEntries)
  const qaTotal = progress.totalQa || progress.totalEntries
  const qaPct = pct(progress.completedQa, qaTotal)
  const eta = estimateEtaSeconds(
    progress.completedEntries,
    progress.totalEntries,
    elapsedS,
  )
  const running = jobStatus === 'running'
  const failed = jobStatus === 'failed'

  const modsLabel = progress.fractionalMods != null && progress.fractionalMods !== progress.completedMods
    ? `${progress.fractionalMods.toFixed(1)} / ${progress.totalMods || '?'}`
    : `${progress.completedMods} / ${progress.totalMods || '?'}`

  const qaPanelItems = groupQaEntries(progress.qaEntries, showAllBatches)

  return (
    <div className="step-card wide translate-run-card">
      <h2 className="step-title">Translating</h2>
      <p className="step-subtitle">
        {state.source} → {state.target} via {state.provider}
        {state.dryRun ? ' (dry run)' : ''}
      </p>

      {(startError || state.error) && (
        <p className="error-msg" style={{ marginBottom: 16 }}>{startError || state.error}</p>
      )}

      {progress.phase && <p className="run-phase">{progress.phase}</p>}

      {progress.modName && (
        <p className="run-detail">
          Mod: <strong>{progress.modName}</strong>
          {progress.currentFile ? ` — ${progress.currentFile}` : ''}
        </p>
      )}

      <div className="progress-block">
        <div className="progress-label">
          <span>Mods</span>
          <span>{modsLabel}</span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${modsPct}%` }} />
        </div>
      </div>

      <div className="progress-block">
        <div className="progress-label">
          <span>Entries</span>
          <span>
            {progress.completedEntries} / {progress.totalEntries || '?'}
            {progress.failed > 0 ? ` (${progress.failed} failed)` : ''}
          </span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill progress-fill--entries" style={{ width: `${entriesPct}%` }} />
        </div>
      </div>

      {state.qaEnabled && (
        <div className="progress-block">
          <div className="progress-label">
            <span>QA</span>
            <span>
              Judged {progress.completedQa} / {qaTotal || '?'} queued
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill progress-fill--qa"
              style={{ width: `${qaPct}%` }}
            />
          </div>
        </div>
      )}

      {running && (
        <p className="run-stats">
          Elapsed: {formatDuration(elapsedS)}
          {eta != null ? ` · ETA: ~${formatDuration(eta)}` : ''}
        </p>
      )}

      <div className={`live-panels${state.qaEnabled ? ' live-panels--dual' : ''}`}>
        <div className="translations-section">
          <p className="translations-heading">Translations</p>
          <div className="translations-panel" ref={panelRef}>
            {progress.translations.length === 0 ? (
              <p className="translations-empty">Waiting for first translation…</p>
            ) : (
              progress.translations.map((t, i) => {
                const delayMs = (progress.translations.length - 1 - i) * 25
                return (
                  <div key={t.uid} className="tr-row" style={{ animationDelay: `${delayMs}ms` }}>
                    <span className="tr-source">{t.source}</span>
                    <span className="tr-arrow">→</span>
                    <span className="tr-target">{t.translated}</span>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {state.qaEnabled && (
          <div className="qa-live-section">
            <div className="qa-live-toolbar">
              <p className="translations-heading qa-live-heading">QA</p>
              <label className="qa-batch-toggle">
                <input
                  type="checkbox"
                  checked={showAllBatches}
                  onChange={e => setShowAllBatches(e.target.checked)}
                />
                Show all batches
              </label>
            </div>
            <div className="qa-live-panel" ref={qaPanelRef}>
              {qaPanelItems.length === 0 ? (
                <p className="translations-empty">Waiting for QA output…</p>
              ) : (
                qaPanelItems.map((item, i) => renderQaPanelItem(item, i, qaPanelItems.length))
              )}
            </div>
          </div>
        )}
      </div>

      <div className="step-actions">
        <button
          className="btn-ghost"
          onClick={() => dispatch({ type: 'SET_STEP', step: 4 })}
          disabled={running}
        >
          ← Back
        </button>
        {running && (
          <button className="btn-danger" onClick={() => void handleCancel()} disabled={cancelling}>
            {cancelling ? 'Cancelling…' : 'Cancel'}
          </button>
        )}
        {failed && (
          <button className="btn-primary" onClick={() => dispatch({ type: 'SET_STEP', step: 6 })}>
            View summary →
          </button>
        )}
      </div>
    </div>
  )
}
