import type { SpikeResult, UploadedImage } from '../types';
import { ANALYZE_TIMEOUT_MS, api, toApiError } from './api';

// Same image_0..image_N form contract as /analyze, but a different endpoint and
// a different model. /spike now fans out over six retrieval queries and calls
// the LLM, so it needs the analyze budget, not a shorter one.
const SPIKE_TIMEOUT_MS = ANALYZE_TIMEOUT_MS;
// TODO:  here is the problem, the model is not loaded in time, so the request is rejected
/// I  ve gootta to track the  soruce issue [long time delay+  model loading] back to fastapi
export async function classifySpikes(

  images: UploadedImage[],
  onUploadProgress?: (fraction: number) => void
): Promise<SpikeResult> {

  const form = new FormData();

  images.forEach((img, i) => form.append(`image_${i}`, img.file, img.name));

  try {

    const { data } = await api.post<SpikeResult>('/spike', form, {
      timeout: SPIKE_TIMEOUT_MS,

      onUploadProgress: (e) => {

        if (!onUploadProgress) return;
        const total = e.total ?? 0;

        onUploadProgress(total > 0 ? Math.min(e.loaded / total, 1) : 0);
      },

    });
    return data;

  } catch (err) {
    // No fallback verdict. 
    throw toApiError(err);
  }
}
