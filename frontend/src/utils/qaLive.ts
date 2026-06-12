import type { QaLiveEntry } from '../types'

const MAX_QA_ENTRIES = 200
let _nextUid = 1

export function nextUid(): number {
  return _nextUid++
}

function hasFixForKey(entries: QaLiveEntry[], key: string): boolean {
  return entries.some(e => e.kind === 'fix' && e.key === key)
}

function priorFlag(entries: QaLiveEntry[], key: string): QaLiveEntry | undefined {
  for (let i = entries.length - 1; i >= 0; i--) {
    const e = entries[i]
    if (e.kind === 'flag' && e.key === key) return e
  }
  return undefined
}

export function appendQaEntry(entries: QaLiveEntry[], entry: QaLiveEntry): QaLiveEntry[] {
  let next = entries
  if (entry.kind === 'fix') {
    next = entries.filter(e => !(e.kind === 'flag' && e.key === entry.key))
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
      original: String(data.original ?? ''),
      fixed: String(data.fixed ?? ''),
      score: flag?.kind === 'flag' ? flag.score : undefined,
      issue: flag?.kind === 'flag' ? flag.issue : undefined,
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

  return null
}

export function shortQaKey(key: string): string {
  const dot = key.lastIndexOf('.')
  return dot >= 0 ? key.slice(dot + 1) : key
}
