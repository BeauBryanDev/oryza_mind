import { useEffect } from 'react';
import Home from './pages/Home';
import { useAppStore } from './stores/appStore';

const HEALTH_POLL_MS = 30000;

export default function App() {

  const checkHealth = useAppStore((s) => s.checkHealth);

  useEffect(() => {
    
    void checkHealth();
    const t = setInterval(() => void checkHealth(), HEALTH_POLL_MS);
    return () => clearInterval(t);
  }, [checkHealth]);

  return <Home />;
}
