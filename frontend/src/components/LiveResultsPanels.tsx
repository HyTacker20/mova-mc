import { memo, useEffect, useRef, type CSSProperties } from 'react'
import type { QaLiveEntry, TranslatedEntry } from '../types'
import {
  formatQaKey,
  formatTextPreview,
  groupQaEntries,
  summarizeCorrectionFailures,
  type QaEntryGroup,
  type QaPanelItem,
} from '../utils/qaLive'

export interface LiveResultsPanelsProps {
  translations: TranslatedEntry[]
  qaEntries: QaLiveEntry[]
  qaEnabled: boolean
  animate?: boolean
  autoScroll?: boolean
  emptyTranslationText?: string
  emptyQaText?: string
}

/** Memoized translation row — avoids re-animating existing rows when new ones arrive. */
const TrRow = memo(function TrRow({
  entry,
  animate,
}: {
  entry: TranslatedEntry
  animate: boolean
}) {
  return (
    <div
      className="tr-row"
      style={animate ? undefined : { animation: 'none' }}
    >
      <span className="tr-source">{entry.source}</span>
      <span className="tr-arrow">→</span>
      <span className="tr-target">{entry.translated}</span>
    </div>
  )
})

function rowStyle(index: number, total: number, animate: boolean): CSSProperties {
  if (!animate) return { animation: 'none' }
  return { animationDelay: `${(total - 1 - index) * 25}ms` }
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
  const issue = group.fix?.issue || group.flag?.issue || null

  return (
    <div key={group.key} className="qa-card" style={style}>
      <div className="qa-card-header">
        <span className="qa-card-key" title={group.key}>{group.displayKey}</span>
        {issue && <span className="qa-badge">⚠ {issue}</span>}
      </div>
      <div className="qa-card-body">
        {group.fix ? (
          <div className="qa-change-line">
            <span className="qa-change-was">{formatTextPreview(group.fix.original)}</span>
            <span className="qa-change-arrow">→</span>
            <span className="qa-change-now">{formatTextPreview(group.fix.fixed)}</span>
          </div>
        ) : group.flag?.translated ? (
          <div className="qa-change-line">
            <span className="qa-change-was">{formatTextPreview(group.flag.translated)}</span>
          </div>
        ) : null}
        {(group.fix?.why || group.flag?.why) && (
          <div className="qa-card-why">{group.fix?.why || group.flag?.why}</div>
        )}
        {failure && !group.fix && (
          <div className="qa-card-failure">{failure}</div>
        )}
        {group.notes.length > 0 && (
          <div className="qa-card-notes">
            {group.notes.map((note, i) => (
              <div key={i} className="qa-card-note">{note}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function renderQaPanelItem(item: QaPanelItem, index: number, total: number, animate: boolean) {
  const style = rowStyle(index, total, animate)
  if (item.type === 'meta') {
    return renderQaMeta(item.entry, style)
  }
  return renderQaGroup(item.group, style)
}

export default function LiveResultsPanels({
  translations,
  qaEntries,
  qaEnabled,
  animate = true,
  autoScroll = true,
  emptyTranslationText = 'Waiting for first translation…',
  emptyQaText = 'Waiting for QA output…',
}: LiveResultsPanelsProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const qaPanelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!autoScroll) return
    const panel = panelRef.current
    if (!panel) return
    panel.scrollTop = panel.scrollHeight
  }, [translations.length, autoScroll])

  useEffect(() => {
    if (!autoScroll) return
    const panel = qaPanelRef.current
    if (!panel) return
    panel.scrollTop = panel.scrollHeight
  }, [qaEntries.length, autoScroll])

  const qaPanelItems = groupQaEntries(qaEntries)

  return (
    <div className={`live-panels${qaEnabled ? ' live-panels--dual' : ''}`}>
      <div className="translations-section">
        <p className="translations-heading">Translations</p>
        <div className="translations-panel" ref={panelRef}>
          {translations.length === 0 ? (
            <p className="translations-empty">{emptyTranslationText}</p>
          ) : (
            translations.map((t) => (
              <TrRow
                key={t.uid}
                entry={t}
                animate={animate}
              />
            ))
          )}
        </div>
      </div>

      {qaEnabled && (
        <div className="qa-live-section">
          <p className="translations-heading qa-live-heading">QA</p>
          <div className="qa-live-panel" ref={qaPanelRef}>
            {qaPanelItems.length === 0 ? (
              <p className="translations-empty">{emptyQaText}</p>
            ) : (
              qaPanelItems.map((item, i) => renderQaPanelItem(item, i, qaPanelItems.length, animate))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
