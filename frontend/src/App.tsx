import { WizardProvider } from './context/WizardContext'
import Wizard from './components/Wizard'

export default function App() {
  return (
    <WizardProvider>
      <Wizard />
    </WizardProvider>
  )
}
