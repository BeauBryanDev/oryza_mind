import { useCallback } from 'react';
import { useSpikeStore } from '../stores/spikeStore';
import { useChatStore } from '../stores/chatStore';
import { classifySpikes } from '../services/spikeService';
import { OryzaApiError } from '../services/api';
import { validateBatch } from '../utils/validators';
import { makeId, makePreviewUrl } from '../utils/imageUtils';
import { MAX_SPIKE_IMAGES } from '../utils/constants';
import type { SpikeResult, UploadedImage } from '../types';

const UPLOAD_CEILING = 45; 
// Percent of the image to upload before reporting progress.

function summarize(result: SpikeResult): string {

  const lines = result.predictions
    .map((p) => {

      const verdict = p.label === 'UNHEALTHY' ? 'Unhealthy spike' : 'Healthy spike';
      const note = p.uncertain ? ', borderline call' : '';

      return `- **${p.filename ?? `Image ${p.imageIndex + 1}`}** — ${verdict}, ${(p.confidence * 100).toFixed(1)}% confidence${note}`;
    })
    .join('\n');

  const header =
    result.unhealthyCount > 0
      ? `Spike check complete. **${result.unhealthyCount} of ${result.totalCount}** panicle${result.totalCount === 1 ? '' : 's'} came back unhealthy:`
      : `Spike check complete. All ${result.totalCount} panicle${result.totalCount === 1 ? '' : 's'} came back healthy:`;

  // This model classifies panicle condition only [health/unhealth] so
  // the plan below is a differential, not a diagnosis. Say so.
  const caveat =
    '\n\nThis check reports panicle condition only; it does not confirm a ' +
    'single disease.';

  // The recommendations go into the chat thread too, so follow-up questions
  // carry them in history and the agent can build on its own advice.
  const advice = result.recommendations?.length
    ? '\n\n**Panicle management:**\n' + result.recommendations.map((r) => `- ${r}`).join('\n')
    : '';

  const source = result.grounded
    ? ''
    : '\n\n_Not drawn from the OryzaMind sources — general agronomic knowledge. ' +
      'Confirm with your local extension service before spraying._';

  return `${header}\n\n${lines}${caveat}${advice}${source}`;
}

export function useSpike() {

  const images = useSpikeStore((s) => s.images);
  const running = useSpikeStore((s) => s.running);
  const result = useSpikeStore((s) => s.result);
  const error = useSpikeStore((s) => s.error);

  const handleFiles = useCallback((fileList: FileList | File[]) => {

    const store = useSpikeStore.getState();
    const arr = Array.from(fileList);
    const check = validateBatch(store.images.length, arr, MAX_SPIKE_IMAGES);

    if (!check.ok) {

      store.setError(check.message ?? 'Invalid file');
      setTimeout(() => useSpikeStore.getState().setError(null), 3500);

      return;
    }
    store.setError(null);
    const mapped: UploadedImage[] = arr.map((file) => ({

      id: makeId(),
      file,
      previewUrl: makePreviewUrl(file),
      name: file.name,
      size: file.size,
    }));

    store.addImages(mapped);
  }, []);

  const run = useCallback(async () => {

    const s = useSpikeStore.getState();
    if (!s.images.length || s.running) return;

    s.setError(null);
    s.setResult(null);
    s.setRunning(true);
    s.setProgress(0);

    try {
      const res = await classifySpikes(s.images, (pct) => {

        useSpikeStore.getState().setProgress(Math.round(pct * UPLOAD_CEILING));
      });

      const store = useSpikeStore.getState();
      store.setResult(res);
      // Snapshot now, while the File objects and their blob: URLs are alive.
      store.setResultPreviews(s.images.map((i) => i.previewUrl));
      store.setProgress(100);
      useChatStore.getState().addMessage({ role: 'assistant', content: summarize(res) });

    } catch (err) {

      const message =
        err instanceof OryzaApiError ? err.message : 'The spike check could not be completed.';
      const store = useSpikeStore.getState();
      store.setProgress(0);
      store.setError(message);

    } finally {
      useSpikeStore.getState().setRunning(false);
    }
  }, []);

  return {

    images,
    running,
    result,
    error,
    handleFiles,
    run,
    removeImage: useSpikeStore.getState().removeImage,
    clearImages: useSpikeStore.getState().clearImages,

  };
}
