import './Wizard.css'
import { useWizard } from '../context/WizardContext'
import Welcome from './steps/Welcome'
import Provider from './steps/Provider'
import Paths from './steps/Paths'
import Advanced from './steps/Advanced'
import Mods from './steps/Mods'
import TranslationRun from './steps/TranslationRun'
import Summary from './steps/Summary'

const STEP_LABELS = ['Welcome', 'Provider', 'Paths', 'Advanced', 'Mods', 'Translate', 'Summary']

export default function Wizard() {
  const { state } = useWizard()
  const { step } = state

  const stepContent = () => {
    switch (step) {
      case 0: return <Welcome />
      case 1: return <Provider />
      case 2: return <Paths />
      case 3: return <Advanced />
      case 4: return <Mods />
      case 5: return <TranslationRun />
      case 6: return <Summary />
      default: return <Welcome />
    }
  }

  return (
    <div className="wizard-layout">
      <header className="wizard-header">
        <span className="wizard-logo">⚒ MovaMC</span>
        <Stepper current={step} labels={STEP_LABELS} />
      </header>
      <main className="wizard-body">
        <div className="step-transition" key={step}>
          {stepContent()}
        </div>
      </main>
    </div>
  )
}

function Stepper({ current, labels }: { current: number; labels: string[] }) {
  return (
    <nav className="stepper" aria-label="Translation progress">
      {labels.map((label, i) => (
        <span
          key={i}
          className={`stepper-dot ${i < current ? 'done' : i === current ? 'active' : ''}`}
          aria-current={i === current ? 'step' : undefined}
        >
          <span className="dot-icon" aria-hidden="true">
            {i < current ? '●' : i === current ? '●' : '○'}
          </span>
          <span className="stepper-label">{label}</span>
        </span>
      ))}
    </nav>
  )
}
