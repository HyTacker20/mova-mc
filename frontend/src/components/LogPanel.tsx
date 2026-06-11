import { useEffect, useRef, useState } from 'react'

interface LogLine {
  text: string
}

interface LogPanelProps {
  visible: boolean
  onClose: () => void
}

export default function LogPanel({ visible, onClose }: LogPanelProps) {
  const [lines, setLines] = useState<string[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!visible) return

    const es = new EventSource('/api/logs/stream')
    es.onmessage = (ev) => {
      try {
        const entry: LogLine = JSON.parse(ev.data)
        setLines(prev => {
          const next = [...prev, entry.text]
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

  // Auto-scroll to bottom when new lines arrive.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  if (!visible) return null

  return (
    <aside className="log-panel">
      <div className="log-panel-header">
        <span className="log-panel-title">Logs</span>
        <button className="log-panel-close" onClick={onClose} aria-label="Close log panel">
          ✕
        </button>
      </div>
      <div className="log-panel-body">
        {lines.length === 0 && <div className="log-panel-empty">Waiting for log output…</div>}
        {lines.map((line, i) => (
          <div key={i} className="log-line">{line}</div>
        ))}
        <div ref={bottomRef} />
      </div>
    </aside>
  )
}
