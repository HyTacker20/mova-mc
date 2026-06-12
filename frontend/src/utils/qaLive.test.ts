import { describe, expect, it } from 'vitest'
import {
  formatQaKey,
  formatTextPreview,
  groupQaEntries,
  summarizeCorrectionFailures,
  stripMcFormatting,
} from './qaLive'
import type { QaLiveEntry } from '../types'

describe('formatQaKey', () => {
  it('uses last segment when distinctive', () => {
    expect(formatQaKey('info.actuallyadditions.gui.respectModInfo')).toBe('respectModInfo')
  })

  it('uses parent for numeric suffix', () => {
    expect(formatQaKey('booklet.actuallyadditions.trials.empoweredOil.text.1')).toBe('text.1')
  })

  it('uses parent for generic name suffix', () => {
    expect(formatQaKey('item.actuallyadditions.coffee.name')).toBe('coffee.name')
  })
})

describe('stripMcFormatting', () => {
  it('removes item tags', () => {
    expect(stripMcFormatting('<item>Біо-Маша<r> текст')).toBe('Біо-Маша текст')
  })
})

describe('formatTextPreview', () => {
  it('truncates long preview', () => {
    const result = formatTextPreview('a'.repeat(120), 40)
    expect(result.endsWith('…')).toBe(true)
  })
})

describe('groupQaEntries', () => {
  it('hides empty batch summaries by default', () => {
    const entries: QaLiveEntry[] = [
      { uid: 1, kind: 'summary', flagged: 0, total: 25, corrected: 0, elapsed: 0 },
    ]
    expect(groupQaEntries(entries)).toEqual([])
  })

  it('groups flag and corrections for same key', () => {
    const entries: QaLiveEntry[] = [
      { uid: 1, kind: 'flag', key: 'item.coffee.name', score: 3, issue: 'russism' },
      { uid: 2, kind: 'correction', key: 'item.coffee.name', accepted: false, attempt: 1, maxAttempts: 3, reason: 'unchanged' },
      { uid: 3, kind: 'correction', key: 'item.coffee.name', accepted: false, attempt: 2, maxAttempts: 3, reason: 'unchanged' },
    ]
    const grouped = groupQaEntries(entries)
    expect(grouped).toHaveLength(1)
    expect(grouped[0].type).toBe('group')
    if (grouped[0].type === 'group') {
      expect(grouped[0].group.displayKey).toBe('coffee.name')
      expect(grouped[0].group.corrections).toHaveLength(2)
      expect(summarizeCorrectionFailures(grouped[0].group)).toContain('unchanged')
    }
  })
})
