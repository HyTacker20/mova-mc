import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import LiveResultsPanels from '../LiveResultsPanels'
import { useWizard } from '../../context/WizardContext'
import { friendlyError } from '../../utils/errors'
import type { JobRequest, WizardState } from '../../types'

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

export default function TranslationRun() {
  const { state, dispatch } = useWizard()
  const { progress, jobStatus } = state
  const [startError, setStartError] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const [elapsedS, setElapsedS] = useState(0)
  const startedRef = useRef(false)
  const esRef = useRef<EventSource | null>(null)
  const stateRef = useRef(state)
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
        dispatch({ type: 'JOB_ERROR', error: friendlyError(job.error ?? `Job ended with status: ${job.status}`) })
      } catch (err) {
        if (!cancelled) {
          dispatch({ type: 'JOB_ERROR', error: friendlyError(String((err as Error).message ?? err)) })
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
          const msg = friendlyError(String((err as Error).message ?? err))
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
      setStartError(friendlyError(String((err as Error).message ?? err)))
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

  const modsLabel = `${progress.completedMods} / ${progress.totalMods || '?'}`

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

      <LiveResultsPanels
        translations={progress.translations}
        qaEntries={progress.qaEntries}
        qaEnabled={state.qaEnabled}
      />

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
