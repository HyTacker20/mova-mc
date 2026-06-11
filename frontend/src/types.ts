export interface ModInfo {
  name: string
  size_bytes: number
  has_lang_files: boolean
  lang_file_count: number
  estimated_entries: number
  selected: boolean
}

export interface ConfigResponse {
  provider: string
  model: string | null
  source: string
  target: string
  workers: number
  output: string | null
  no_cache: boolean
  hint_lang: string | null
  glossary_path: string | null
  output_mode: string
  config_path: string | null
}

export interface ProviderInfo {
  id: string
  label: string
  requires_key: boolean
  key_env: string | null
  default_model: string | null
  models: string[]
}

export interface QaRequest {
  enabled: boolean
  provider: string | null
  model: string | null
  threshold: number
  max_attempts: number
  streaming: boolean
  chunk_size: number
  judge_workers: number
}

export interface RateLimitRequest {
  rpm: number | null
  burst: number | null
  judge_rpm: number | null
  judge_burst: number | null
}

export interface JobRequest {
  source: string
  target: string
  provider: string
  model: string | null
  workers: number
  path: string
  output: string
  output_mode: string
  no_cache: boolean
  dry_run: boolean
  hint_lang: string | null
  glossary_path: string | null
  chunk_mode: string
  selected_mods: string[]
  qa: QaRequest
  rate_limit: RateLimitRequest
}

export interface FileStatsResponse {
  path: string
  file_type: string
  entries_total: number
  entries_translated: number
  entries_failed: number
}

export interface ModStatsResponse {
  name: string
  skipped: boolean
  translated_entries: number
  total_entries: number
  failed_entries: number
  files: FileStatsResponse[]
}

export interface OverallStatsResponse {
  provider: string
  source_lang: string
  target_lang: string
  translated_mods: number
  total_mods: number
  translated_entries: number
  total_entries: number
  failed_entries: number
  duration_seconds: number
  mods: ModStatsResponse[]
}

export interface ProgressState {
  phase: string
  modName: string
  currentFile: string
  completedMods: number
  totalMods: number
  fractionalMods: number | null
  completedEntries: number
  totalEntries: number
  logs: string[]
  translations: { key: string; source: string; translated: string }[]
  failed: number
}

export interface WizardState {
  step: number
  // Step 1 — Provider
  provider: string
  model: string
  // Step 2 — Paths
  source: string
  target: string
  modsPath: string
  outputPath: string
  outputMode: string
  // Step 3 — Advanced
  workers: number
  noCache: boolean
  dryRun: boolean
  hintLang: string
  qaEnabled: boolean
  qaProvider: string
  qaModel: string
  qaThreshold: number
  qaMaxAttempts: number
  // Step 4 — Mods
  mods: ModInfo[]
  selectedMods: string[]
  // Step 5 — Run
  jobId: string | null
  jobStatus: string
  progress: ProgressState
  // Step 6 — Summary
  stats: OverallStatsResponse | null
  error: string | null
  // Shared — path to the config file being used
  configPath: string | null
}

export type WizardAction =
  | { type: 'SET_STEP'; step: number }
  | { type: 'SET_PROVIDER'; provider: string; model: string }
  | { type: 'SET_PATHS'; source: string; target: string; modsPath: string; outputPath: string; outputMode: string }
  | { type: 'SET_ADVANCED'; workers: number; noCache: boolean; dryRun: boolean; hintLang: string; qaEnabled: boolean; qaProvider: string; qaModel: string; qaThreshold: number; qaMaxAttempts: number }
  | { type: 'SET_MODS'; mods: ModInfo[] }
  | { type: 'TOGGLE_MOD'; name: string }
  | { type: 'SELECT_ALL_MODS' }
  | { type: 'DESELECT_ALL_MODS' }
  | { type: 'JOB_STARTED'; jobId: string }
  | { type: 'PROGRESS'; event: string; data: Record<string, unknown> }
  | { type: 'JOB_DONE'; stats: OverallStatsResponse }
  | { type: 'JOB_ERROR'; error: string }
  | { type: 'RESET' }
  | { type: 'SET_CONFIG_PATH'; path: string | null }
