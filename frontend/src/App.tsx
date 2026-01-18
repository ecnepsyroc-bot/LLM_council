import { useEffect } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { DeliberationView } from './components/layout/DeliberationView';
import { useCouncilStore } from './store/councilStore';
import { useSettingsStore } from './store/settingsStore';

function App() {
  const { fetchConfig } = useCouncilStore();
  const { applyTheme } = useSettingsStore();

  useEffect(() => {
    fetchConfig();
    // Apply theme on initial load
    applyTheme();
  }, [fetchConfig, applyTheme]);

  return (
    <AppLayout>
      <DeliberationView />
    </AppLayout>
  );
}

export default App;
