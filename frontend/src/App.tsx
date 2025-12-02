import { useEffect } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { DeliberationView } from './components/layout/DeliberationView';
import { useCouncilStore } from './store/councilStore';

function App() {
  // Force rebuild
  const { fetchConfig } = useCouncilStore();

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  return (
    <AppLayout>
      <DeliberationView />
    </AppLayout>
  );
}

export default App;
