import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { SpikeResult, UploadedImage } from '../types';
import { revokePreviewUrl } from '../utils/imageUtils';
import { MAX_SPIKE_IMAGES } from '../utils/constants';

// Kept out of analysisStore on purpose: two independent drop zones, two
// independent results. Sharing `images` would send leaf photos to the spike
// It was the easiest fix  for v1,  it might be a better way.  bit i m in a rush to deliver
interface SpikeState {

  images: UploadedImage[];
  running: boolean;
  progress: number;
  result: SpikeResult | null;
  // Preview URLs snapshotted when the run succeeded, so the results panel can
  // show the panicle photos even after the upload list changes. blob: URLs, so
  // they are session-only and never persisted.
  resultPreviews: string[];
  error: string | null;
  addImages: (imgs: UploadedImage[]) => void;
  removeImage: (id: string) => void;
  clearImages: () => void;
  setRunning: (v: boolean) => void;
  setProgress: (p: number) => void;
  setResult: (r: SpikeResult | null) => void;
  setResultPreviews: (urls: string[]) => void;
  setError: (e: string | null) => void;
}

const STORAGE_KEY = 'oryza-spike';

export const useSpikeStore = create<SpikeState>()(

  persist(

    (set, get) => ({

      images: [],
      running: false,
      progress: 0,
      result: null,
      resultPreviews: [],
      error: null,

      addImages: (imgs) =>
        set({ images: [...get().images, ...imgs].slice(0, MAX_SPIKE_IMAGES) }),

      removeImage: (id) => {

        const img = get().images.find((i) => i.id === id);
        if (img) revokePreviewUrl(img.previewUrl);
        set({ images: get().images.filter((i) => i.id !== id) });
      },
      clearImages: () => {

        get().images.forEach((i) => revokePreviewUrl(i.previewUrl));
        set({ images: [], result: null, resultPreviews: [], error: null, progress: 0 });
      },

      setRunning: (running) => set({ running }),
      setProgress: (progress) => set({ progress }),
      setResult: (result) => set({ result }),
      setResultPreviews: (resultPreviews) => set({ resultPreviews }),
      setError: (error) => set({ error }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
 
      version: 2,
 
      partialize: (state) => ({ result: state.result }),
      onRehydrateStorage: () => (state) => {
        state?.setRunning(false);
        state?.setProgress(state.result ? 100 : 0);
        state?.setError(null);
      },
    }
  )
);
