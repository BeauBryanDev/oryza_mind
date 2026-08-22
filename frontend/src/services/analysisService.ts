import type { AnalysisResult, HealthResponse, UploadedImage } from '../types';
import { ANALYZE_TIMEOUT_MS, api, toApiError } from './api';

// Field names must be image_0..image_2: the backend reads the form by prefix
// and rejects a fourth file rather than ignoring it.
export async function analyzeImages(
  images: UploadedImage[],
  onUploadProgress?: (fraction: number) => void
): Promise<AnalysisResult> {
  const form = new FormData();
  images.forEach((img, i) => form.append(`image_${i}`, img.file, img.name));

  try {
    const { data } = await api.post<AnalysisResult>('/analyze', form, {
      timeout: ANALYZE_TIMEOUT_MS,
      onUploadProgress: (e) => {
        if (!onUploadProgress) return;
        const total = e.total ?? 0;
        onUploadProgress(total > 0 ? Math.min(e.loaded / total, 1) : 0);
      },
    });
    return data;
  } catch (err) {
    // No demo fallback. Inventing a diagnosis is worse than reporting failure.
    throw toApiError(err);
  }
}

export async function fetchHealth(): Promise<HealthResponse | null> {
  try {
    const { data } = await api.get<HealthResponse>('/health', { timeout: 5000 });
    return data;
    // No fallback verdict.
  } catch {
    return null;
  }
}
