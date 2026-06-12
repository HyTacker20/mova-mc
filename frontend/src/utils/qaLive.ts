import type { QaLiveEntry } from '../types'

const MAX_QA_ENTRIES = 200
const GENERIC_SUFFIXES = new Set(['name', 'text', 'desc', 'title', 'tooltip', 'label'])
const MC_TAG_RE = /<\/?(?:item|imp|r|bold|italic|underlined|strikethrough|c|link)[^>]*>/gi
const SECTION_CODE_RE = /§./g

let _nextUid = 1

export function nextUid(): number {
  return _nextUid++
}

export function formatQaKey(key: string): string {
  const parts = key.split('.')
  if (parts.length <= 1) return key
  const last = parts[parts.length - 1]
  if (/^\d+$/.test(last) || GENERIC_SUFFIXES.has(last.toLowerCase())) {
    if (parts.length >= 2) return `${parts[parts.length - 2]}.${last}`
  }
  return last
}

/** @deprecated use formatQaKey */
export function shortQaKey(key: string): string {
  return formatQaKey(key)
}

export function stripMcFormatting(text: string): string {
  return text.replace(MC_TAG_RE, '').replace(SECTION_CODE_RE, '').trim()
}

export function truncatePreview(text: string, maxLen = 80): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen - 1).trimEnd() + '…'
}

export function formatTextPreview(text: string, maxLen = 80): string {
  return truncatePreview(stripMcFormatting(text), maxLen)
}

export function formatTextChangePreview(original: string, fixed: string, maxLen = 60): string {
  return `"${formatTextPreview(original, maxLen)}" → "${formatTextPreview(fixed, maxLen)}"`
}

function hasFixForKey(entries: QaLiveEntry[], key: string): boolean {
  return entries.some(e => e.kind === 'fix' && e.key === key)
}

function priorFlag(entries: QaLiveEntry[], key: string): QaLiveEntry | undefined {
  for (let i = entries.length - 1; i >= 0; i--) {
    const e = entries[i]
    if ((e.kind === 'flag' || e.kind === 'info') && e.key === key) return e
  }
  return undefined
}

export function appendQaEntry(entries: QaLiveEntry[], entry: QaLiveEntry): QaLiveEntry[] {
  let next = entries
  if (entry.kind === 'fix') {
    next = entries.filter(e => !((e.kind === 'flag' || e.kind === 'info') && e.key === entry.key))
  }
  if (entry.kind === 'done') {
    next = entries.filter(e => e.kind !== 'done')
  }
  const updated = [...next, entry]
  return updated.length > MAX_QA_ENTRIES ? updated.slice(-MAX_QA_ENTRIES) : updated
}

/** Map a progress SSE event to a QA live entry, or null to skip. */
export function qaEventToEntry(
  event: string,
  data: Record<string, unknown>,
  entries: QaLiveEntry[],
): QaLiveEntry | null {
  if (event === 'qa_inline_fix') {
    const key = String(data.key ?? '?')
    const flag = priorFlag(entries, key)
    return {
      uid: nextUid(),
      kind: 'fix',
      key,
      source: data.source != null ? String(data.source) : undefined,
      original: String(data.original ?? ''),
      fixed: String(data.fixed ?? ''),
      score: flag?.kind === 'flag' || flag?.kind === 'info' ? flag.score : undefined,
      issue: flag?.kind === 'flag' || flag?.kind === 'info' ? flag.issue : undefined,
      why: data.why != null ? String(data.why) : undefined,
    }
  }

  if (event === 'qa_verdict') {
    if (!data.is_flagged) return null
    const key = String(data.key ?? '?')
    if (hasFixForKey(entries, key)) return null
    return {
      uid: nextUid(),
      kind: 'flag',
      key,
      score: Number(data.score ?? 0),
      issue: data.issue != null ? String(data.issue) : undefined,
      source: data.source != null ? String(data.source) : undefined,
      translated: data.translated != null ? String(data.translated) : undefined,
      why: data.why != null ? String(data.why) : undefined,
    }
  }

  if (event === 'qa_correction') {
    return {
      uid: nextUid(),
      kind: 'correction',
      key: String(data.key ?? '?'),
      accepted: Boolean(data.accepted),
      attempt: Number(data.attempt ?? 0),
      maxAttempts: Number(data.max_attempts ?? 1),
      reason: data.reason != null ? String(data.reason) : undefined,
      source: data.source != null ? String(data.source) : undefined,
      original: data.original != null ? String(data.original) : undefined,
      corrected: data.corrected != null ? String(data.corrected) : undefined,
      why: data.why != null ? String(data.why) : undefined,
    }
  }

  if (event === 'qa_inline_status' || event === 'qa_start') {
    const message = data.message != null
      ? String(data.message)
      : `QA active (${String(data.provider ?? '')}/${String(data.model ?? 'default')})`
    return { uid: nextUid(), kind: 'status', message }
  }

  if (event === 'qa_inline_judging') {
    const count = Number(data.count ?? 0)
    return { uid: nextUid(), kind: 'status', message: `→ judging ${count} item(s)…` }
  }

  if (event === 'qa_inline_summary') {
    return {
      uid: nextUid(),
      kind: 'summary',
      flagged: Number(data.flagged ?? 0),
      total: Number(data.total ?? 0),
      corrected: Number(data.corrected ?? 0),
      elapsed: Number(data.elapsed ?? 0),
    }
  }

  if (event === 'qa_done') {
    return {
      uid: nextUid(),
      kind: 'done',
      flagged: Number(data.flagged ?? 0),
      corrected: Number(data.corrected ?? 0),
    }
  }

  if (event === 'qa_warning') {
    return {
      uid: nextUid(),
      kind: 'warning',
      key: String(data.key ?? '?'),
      message: String(data.message ?? ''),
    }
  }

  if (event === 'qa_inline_error') {
    return { uid: nextUid(), kind: 'error', message: String(data.message ?? 'Judge failed') }
  }

  if (event === 'qa_inline_note') {
    return {
      uid: nextUid(),
      kind: 'note',
      key: data.key != null ? String(data.key) : undefined,
      message: String(data.message ?? ''),
    }
  }

  return null
}

export interface QaEntryGroup {
  key: string
  displayKey: string
  source?: string
  flag?: { score: number; issue?: string; translated?: string; why?: string }
  fix?: { original: string; fixed: string; score?: number; issue?: string; why?: string }
  corrections: Array<{
    accepted: boolean
    attempt: number
    maxAttempts: number
    reason?: string
  }>
  notes: string[]
}

export type QaPanelItem =
  | { type: 'meta'; entry: QaLiveEntry }
  | { type: 'group'; group: QaEntryGroup }

function mergeIntoGroup(group: QaEntryGroup, entry: QaLiveEntry): void {
  if (entry.kind === 'flag' || entry.kind === 'info') {
    group.flag = { score: entry.score, issue: entry.issue, translated: entry.translated, why: entry.why }
    if (entry.source) group.source = entry.source
  } else if (entry.kind === 'fix') {
    group.fix = {
      original: entry.original,
      fixed: entry.fixed,
      score: entry.score,
      issue: entry.issue,
      why: entry.why,
    }
    if (entry.source) group.source = entry.source
    group.flag = undefined
  } else if (entry.kind === 'correction') {
    group.corrections.push({
      accepted: entry.accepted,
      attempt: entry.attempt,
      maxAttempts: entry.maxAttempts,
      reason: entry.reason,
    })
  } else if (entry.kind === 'note') {
    group.notes.push(entry.message)
  }
}

function newGroupFromEntry(entry: QaLiveEntry & { key: string }): QaEntryGroup {
  const group: QaEntryGroup = {
    key: entry.key,
    displayKey: formatQaKey(entry.key),
    corrections: [],
    notes: [],
  }
  mergeIntoGroup(group, entry)
  return group
}

/** Group key-based QA events into cards; filter empty batch summaries by default. */
export function groupQaEntries(entries: QaLiveEntry[], showAllBatches = false): QaPanelItem[] {
  const out: QaPanelItem[] = []
  const groupIndex = new Map<string, number>()

  for (const entry of entries) {
    if (entry.kind === 'summary') {
      if (!showAllBatches && entry.flagged === 0 && entry.corrected === 0) continue
      out.push({ type: 'meta', entry })
      continue
    }

    if (
      entry.kind === 'status'
      || entry.kind === 'done'
      || entry.kind === 'error'
      || (entry.kind === 'warning' && entry.key === '')
    ) {
      out.push({ type: 'meta', entry })
      continue
    }

    if (!('key' in entry) || !entry.key) {
      out.push({ type: 'meta', entry })
      continue
    }

    const existing = groupIndex.get(entry.key)
    if (existing !== undefined) {
      const item = out[existing]
      if (item.type === 'group') mergeIntoGroup(item.group, entry)
    } else {
      const group = newGroupFromEntry(entry as QaLiveEntry & { key: string })
      groupIndex.set(entry.key, out.length)
      out.push({ type: 'group', group })
    }
  }

  return out
}

/** Summarise correction failures for a group card footer. */
export function summarizeCorrectionFailures(group: QaEntryGroup): string | null {
  const failed = group.corrections.filter(c => !c.accepted)
  if (failed.length === 0) return null
  const last = failed[failed.length - 1]
  if (last.reason) {
    return `✗ failed after ${failed.length} attempt(s) — ${last.reason}`
  }
  return `✗ failed after ${failed.length} attempt(s)`
}
