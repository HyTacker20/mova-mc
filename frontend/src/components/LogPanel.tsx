import { useEffect, useRef, useState } from 'react'

interface LogLine {
  text: string
  level?: string
  category?: string
}

interface LogPanelProps {
  visible: boolean
  onClose: () => void
}

type TabId = 'all' | 'translation' | 'qa' | 'other'

const TABS: { id: TabId; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'translation', label: 'Translation' },
  { id: 'qa', label: 'QA' },
  { id: 'other', label: 'Other' },
]

function lineLevel(entry: LogLine): string {
  if (entry.level) return entry.level.toLowerCase()
  const match = entry.text.match(/^(INFO|WARNING|ERROR|DEBUG|TRACE|SUCCESS):/)
  return match ? match[1].toLowerCase() : 'info'
}

export default function LogPanel({ visible, onClose }: LogPanelProps) {
  const [lines, setLines] = useState<LogLine[]>([])
  const [activeTab, setActiveTab] = useState<TabId>('all')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!visible) return

    const es = new EventSource('/api/logs/stream')
    es.onmessage = (ev) => {
      try {
        const entry: LogLine = JSON.parse(ev.data)
        setLines(prev => {
          const next = [...prev, { text: entry.text, level: entry.level, category: entry.category }]
          return next.length > 500 ? next.slice(-500) : next
        })
      } catch {
        /* ignore malformed */
      }
    }
    es.onerror = () => {
      // SSE will auto-reconnect; no action needed.
    }
    return () => es.close()
  }, [visible])

  const filteredLines = lines.filter(line => {
    if (activeTab === 'all') return true
    if (activeTab === 'translation') return line.category === 'translation'
    if (activeTab === 'qa') return line.category === 'qa'
    return line.category !== 'translation' && line.category !== 'qa'
  })

  // Auto-scroll to bottom when new lines arrive.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [filteredLines])

  if (!visible) return null

  return (
    <aside className="log-panel">
      <div className="log-panel-header">
        <div className="log-panel-tabs">
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`log-panel-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button className="log-panel-close" onClick={onClose} aria-label="Close log panel">
          ✕
        </button>
      </div>
      <div className="log-panel-body">
        {filteredLines.length === 0 && (
          <div className="log-panel-empty">
            {activeTab === 'all' ? 'Waiting for log output…' : `No ${activeTab} logs yet…`}
          </div>
        )}
        {filteredLines.map((line, i) => {
          const levelCls = `log-line--${lineLevel(line)}`
          const qaCls = line.category === 'qa' ? ' log-line--qa' : ''
          return <div key={i} className={`log-line ${levelCls}${qaCls}`}>{line.text}</div>
        })}
        <div ref={bottomRef} />
      </div>
    </aside>
  )
}
