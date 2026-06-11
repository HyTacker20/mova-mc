import { useWizard } from '../../context/WizardContext'

export default function Welcome() {
  const { dispatch } = useWizard()
  return (
    <div className="step-card" style={{ textAlign: 'center', maxWidth: 520 }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>⚒</div>
      <h1 className="step-title">MovaMC</h1>
      <p className="step-subtitle" style={{ marginBottom: 8 }}>
        Translate Minecraft mod language files using AI or Google Translate.
      </p>
      <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 32 }}>
        Supports JSON, LANG, and MCFUNCTION formats with placeholder
        validation, glossary injection, and LLM-as-judge QA.
      </p>
      <button className="btn-primary" style={{ fontSize: 15, padding: '10px 32px' }}
        onClick={() => dispatch({ type: 'SET_STEP', step: 1 })}>
        Get Started →
      </button>
    </div>
  )
}
