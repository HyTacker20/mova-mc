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

  return (
    <div className="wizard-layout">
      <header className="wizard-header">
        <span className="wizard-logo">⚒ MovaMC</span>
        <Stepper current={step} labels={STEP_LABELS} />
      </header>
      <main className="wizard-body">
        {step === 0 && <Welcome />}
        {step === 1 && <Provider />}
        {step === 2 && <Paths />}
        {step === 3 && <Advanced />}
        {step === 4 && <Mods />}
        {step === 5 && <TranslationRun />}
        {step === 6 && <Summary />}
      </main>
    </div>
  )
}

function Stepper({ current, labels }: { current: number; labels: string[] }) {
  return (
    <nav className="stepper">
      {labels.map((label, i) => (
        <span
          key={i}
          className={`stepper-dot ${i < current ? 'done' : i === current ? 'active' : ''}`}
          title={label}
        >
          {i < current ? '●' : i === current ? '●' : '○'}
          <span className="stepper-label">{label}</span>
        </span>
      ))}
    </nav>
  )
}
