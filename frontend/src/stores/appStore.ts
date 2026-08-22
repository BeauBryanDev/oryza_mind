import { create } from 'zustand';
import type { HealthResponse } from '../types';
import { fetchHealth } from '../services/analysisService';

export type MobileTab = 'analysis' | 'chat' | 'history' | 'scan' | 'guide' | 'settings';
export type BottomNavKey = 'home' | 'history' | 'scan' | 'guide' | 'settings';

interface AppState {

  health: HealthResponse | null;
  backendOnline: boolean;
  modelOnline: boolean;
  spikeModelOnline: boolean;
  knowledgeBaseOnline: boolean;
  serviceOnline: boolean;
  mobileTab: MobileTab;
  bottomNav: BottomNavKey;
  checkHealth: () => Promise<void>;
  setServiceOnline: (v: boolean) => void;
  setMobileTab: (t: MobileTab) => void;
  setBottomNav: (t: AppState['bottomNav']) => void;
}

export const useAppStore = create<AppState>((set) => ({
  health: null,
  // Start offline and let /health prove otherwise. Defaulting to true showed
  // green pills for a backend that was never contacted.
  backendOnline: false,
  modelOnline: false,
  spikeModelOnline: false,
  knowledgeBaseOnline: false,
  serviceOnline: true,
  mobileTab: 'chat',
  bottomNav: 'home',

  checkHealth: async () => {

    const health = await fetchHealth();

    set({
      health,
      backendOnline: health !== null,
      // The two dependencies fail independently: the model can load while
      // Weaviate is unreachable, which is `status: degraded`.
      modelOnline: health?.modelLoaded ?? false,
      // Loads independently of the leaf detector: one file can be missing
      // while the other serves fine.
      spikeModelOnline: health?.spikeModelLoaded ?? false,
      knowledgeBaseOnline: health?.weaviateReady ?? false,
    });
  },

  setServiceOnline: (v) => set({ serviceOnline: v }),
  setMobileTab: (mobileTab) => set({ mobileTab }),
  setBottomNav: (bottomNav) => {
    // Map bottom nav key → content tab so both states stay in sync
    const tabMap: Record<BottomNavKey, MobileTab> = {
      home: 'chat',
      scan: 'scan',
      history: 'history',
      guide: 'guide',
      settings: 'settings',
    };
    set({ bottomNav, mobileTab: tabMap[bottomNav] });
  },
  
}));
