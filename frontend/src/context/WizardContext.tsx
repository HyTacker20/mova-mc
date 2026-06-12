import { createContext, useContext, useReducer, type Dispatch } from 'react'
import type { ModInfo, OverallStatsResponse, ProgressState, TranslatedEntry, WizardAction, WizardState } from '../types'
import { appendQaEntry, nextUid, qaEventToEntry } from '../utils/qaLive'

const INITIAL_PROGRESS: ProgressState = {
  phase: '',
  modName: '',
  currentFile: '',
  completedMods: 0,
  totalMods: 0,
  fractionalMods: null,
  completedEntries: 0,
  totalEntries: 0,
  completedQa: 0,
  totalQa: 0,
  logs: [],
  translations: [],
  qaEntries: [],
  failed: 0,
}

function estimatedEntriesForMods(mods: ModInfo[], selectedNames: string[]): number {
  const selected = new Set(selectedNames)
  return mods.filter(m => selected.has(m.name)).reduce((sum, m) => sum + m.estimated_entries, 0)
}

export const INITIAL_STATE: WizardState = {
  step: 0,
  provider: 'google',
  model: '',
  source: 'en_US',
  target: 'uk_UA',
  modsPath: './mods',
  outputPath: './translated_mods',
  outputMode: 'separate',
  workers: 4,
  noCache: false,
  dryRun: false,
  hintLang: '',
  qaEnabled: false,
  qaProvider: '',
  qaModel: '',
  qaThreshold: 3,
  qaMaxAttempts: 2,
  qaChunkSize: 25,
  qaJudgeWorkers: 2,
  qaCorrectorModel: '',
  mods: [],
  selectedMods: [],
  jobId: null,
  jobStatus: '',
  progress: INITIAL_PROGRESS,
  stats: null,
  error: null,
  configPath: null,
}

function MAX_LOGS(logs: string[], line: string): string[] {
  const next = [...logs, line]
  return next.length > 300 ? next.slice(-300) : next
}

function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.step }

    case 'SET_PROVIDER':
      return { ...state, provider: action.provider, model: action.model }

    case 'SET_PATHS':
      return {
        ...state,
        source: action.source,
        target: action.target,
        modsPath: action.modsPath,
        outputPath: action.outputPath,
        outputMode: action.outputMode,
      }

    case 'SET_ADVANCED':
      return {
        ...state,
        workers: action.workers,
        noCache: action.noCache,
        dryRun: action.dryRun,
        hintLang: action.hintLang,
        qaEnabled: action.qaEnabled,
        qaProvider: action.qaProvider,
        qaModel: action.qaModel,
        qaThreshold: action.qaThreshold,
        qaMaxAttempts: action.qaMaxAttempts,
        qaChunkSize: action.qaChunkSize,
        qaJudgeWorkers: action.qaJudgeWorkers,
        qaCorrectorModel: action.qaCorrectorModel,
      }

    case 'SET_MODS': {
      const mods = action.mods
      const selected = mods.filter(m => m.selected).map(m => m.name)
      return { ...state, mods, selectedMods: selected }
    }

    case 'TOGGLE_MOD': {
      const exists = state.selectedMods.includes(action.name)
      const selectedMods = exists
        ? state.selectedMods.filter(n => n !== action.name)
        : [...state.selectedMods, action.name]
      return { ...state, selectedMods }
    }

    case 'SELECT_ALL_MODS':
      return { ...state, selectedMods: state.mods.map(m => m.name) }

    case 'DESELECT_ALL_MODS':
      return { ...state, selectedMods: [] }

    case 'JOB_STARTED': {
      const totalEntries = estimatedEntriesForMods(state.mods, state.selectedMods)
      return {
        ...state,
        jobId: action.jobId,
        jobStatus: 'running',
        progress: {
          ...INITIAL_PROGRESS,
          totalMods: state.selectedMods.length,
          totalEntries,
          totalQa: state.qaEnabled ? totalEntries : 0,
        },
        error: null,
      }
    }

    case 'PROGRESS': {
      const { event, data } = action
      const p = state.progress

      if (event === 'title') {
        return { ...state, progress: { ...p, phase: String(data.text ?? '') } }
      }
      if (event === 'mod_start') {
        return {
          ...state,
          progress: {
            ...p,
            modName: String(data.mod_name ?? ''),
            totalEntries: Number(data.entry_count ?? p.totalEntries),
          },
        }
      }
      if (event === 'mod_file_start') {
        return { ...state, progress: { ...p, currentFile: String(data.file_path ?? '') } }
      }
      if (event === 'entry_progress') {
        return {
          ...state,
          progress: {
            ...p,
            completedEntries: Number(data.done ?? 0),
            totalEntries: Number(data.total ?? p.totalEntries),
          },
        }
      }
      if (event === 'overall_progress') {
        const fractional = data.fractional_mods
        const totalEntries = Number(data.total_entries ?? 0)
        const next: ProgressState = {
          ...p,
          completedMods: Number(data.completed_mods ?? 0),
          totalMods: Number(data.total_mods ?? 0),
          fractionalMods: fractional != null ? Number(fractional) : null,
          completedEntries: Number(data.completed_entries ?? 0),
          totalEntries,
          failed: Number(data.failed_entries ?? 0),
        }
        if (state.qaEnabled && totalEntries > 0) {
          next.totalQa = totalEntries
        }
        return { ...state, progress: next }
      }
      if (event === 'qa_progress') {
        // Dynamic denominator: track the max queued count seen so far.
        // The backend reports _qa_queued as 'total' — the number of
        // items queued for QA at this moment, not the absolute total.
        const queued = Number(data.total ?? 0)
        const judged = Number(data.done ?? 0)
        return {
          ...state,
          progress: {
            ...p,
            completedQa: judged,
            totalQa: Math.max(p.totalQa, queued, judged),
          },
        }
      }
      if (event === 'mod_file_complete') {
        const filePath = String(data.file_path ?? '')
        const name = filePath.split(/[/\\]/).pop() || filePath
        const durationMs = Number(data.duration_ms ?? 0)
        const errors = Number(data.errors ?? 0)
        const errPart = errors > 0 ? `, ${errors} failed` : ''
        const line = `${name}: done in ${(durationMs / 1000).toFixed(1)}s${errPart}`
        return { ...state, progress: { ...p, logs: MAX_LOGS(p.logs, line) } }
      }
      if (event === 'mod_complete') {
        const name = String(data.mod_name ?? '')
        const t = Number(data.total ?? 0)
        const done = Number(data.translated ?? 0)
        const fail = Number(data.failed ?? 0)
        const line = fail > 0
          ? `✓ ${name} (${done}/${t}, ${fail} failed)`
          : `✓ ${name} (${done}/${t})`
        return { ...state, progress: { ...p, logs: MAX_LOGS(p.logs, line) } }
      }
      if (event === 'translated_entry') {
        const src = String(data.source ?? '')
        const trn = String(data.translated ?? '')
        const t: TranslatedEntry = {
          uid: nextUid(),
          key: String(data.key ?? ''),
          source: src,
          translated: trn,
        }
        return {
          ...state,
          progress: {
            ...p,
            translations: p.translations.length > 200
              ? [...p.translations.slice(-200), t]
              : [...p.translations, t],
          },
        }
      }
      if (event === 'error') {
        return { ...state, error: String(data.text ?? 'Unknown error') }
      }
      if (event.startsWith('qa_')) {
        const entry = qaEventToEntry(event, data, p.qaEntries)
        if (entry) {
          return {
            ...state,
            progress: { ...p, qaEntries: appendQaEntry(p.qaEntries, entry) },
          }
        }
      }
      return state
    }

    case 'JOB_DONE':
      return { ...state, jobStatus: 'done', stats: action.stats }

    case 'JOB_ERROR':
      return { ...state, jobStatus: 'failed', error: action.error }

    case 'RESET':
      return { ...INITIAL_STATE }

    case 'SET_CONFIG_PATH':
      return { ...state, configPath: action.path }

    default:
      return state
  }
}

interface WizardContextValue {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

const WizardContext = createContext<WizardContextValue | null>(null)

export function WizardProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(wizardReducer, INITIAL_STATE)
  return <WizardContext.Provider value={{ state, dispatch }}>{children}</WizardContext.Provider>
}

export function useWizard(): WizardContextValue {
  const ctx = useContext(WizardContext)
  if (!ctx) throw new Error('useWizard must be used inside WizardProvider')
  return ctx
}
