import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { AnalysisResult, PipelineStage, UploadedImage } from '../types';
import { revokePreviewUrl } from '../utils/imageUtils';

interface AnalysisState {
// 
  images: UploadedImage[];
  stage: PipelineStage;
  progress: number;
  result: AnalysisResult | null;
  error: string | null;
  activeImageIndex: number;
  addImages: (imgs: UploadedImage[]) => void;
  removeImage: (id: string) => void;
  clearImages: () => void;
  setStage: (s: PipelineStage) => void;
  setProgress: (p: number) => void;
  setResult: (r: AnalysisResult | null) => void;
  setError: (e: string | null) => void;
  setActiveImageIndex: (i: number) => void;
}

const STORAGE_KEY = 'oryza-analysis';

export const useAnalysisStore = create<AnalysisState>()(

  persist(

    (set, get) => ({

      images: [],
      stage: 'IDLE',
      progress: 0,
      result: null,
      error: null,
      activeImageIndex: 0,

      addImages: (imgs) => set({ images: [...get().images, ...imgs].slice(0, 3) }),

      removeImage: (id) => {

        const img = get().images.find((i) => i.id === id);
        if (img) revokePreviewUrl(img.previewUrl);

        set({ images: get().images.filter((i) => i.id !== id) });

      },
      clearImages: () => {
        get().images.forEach((i) => revokePreviewUrl(i.previewUrl));
        set({ images: [] });
      },
      setStage: (stage) => set({ stage }),
      setProgress: (progress) => set({ progress }),
      setResult: (result) => set({ result }),
      setError: (error) => set({ error }),
      setActiveImageIndex: (activeImageIndex) => set({ activeImageIndex }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      version: 1,
      // Only the result survives a refresh, and it must: chat sends it back to
      // the agent as vision context, and without it retrieval silently drops
      // the disease_name filter. `images` holds File objects and blob: preview
      // URLs, neither of which survives serialization.
      partialize: (state) => ({

        result: state.result,
        activeImageIndex: state.activeImageIndex,
        stage: state.result ? ('COMPLETED' as PipelineStage) : ('IDLE' as PipelineStage),
      }),

      onRehydrateStorage: () => (state) => {

        // Progress and errors describe a request that is over.
        state?.setProgress(state.result ? 100 : 0);
        state?.setError(null);
        
      },
    }
  )
);
