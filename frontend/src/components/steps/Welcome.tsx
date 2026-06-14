import { useWizard } from '../../context/WizardContext'

export default function Welcome() {
  const { dispatch } = useWizard()
  return (
    <div className="step-card welcome-card">
      <div className="welcome-icon" aria-hidden="true">⚒</div>
      <h1 className="step-title">MovaMC</h1>
      <p className="step-subtitle">
        Translate Minecraft mod language files using AI or Google Translate.
      </p>
      <p className="welcome-desc">
        Supports JSON, LANG, and MCFUNCTION formats with placeholder
        validation, glossary injection, and LLM-as-judge QA.
      </p>
      <button
        className="btn-primary"
        style={{ fontSize: 15, padding: '10px 32px' }}
        onClick={() => dispatch({ type: 'SET_STEP', step: 1 })}
      >
        Get Started →
      </button>
    </div>
  )
}
