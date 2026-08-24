import { useCallback } from 'react';
import { useAnalysisStore } from '../stores/analysisStore';
import { useChatStore } from '../stores/chatStore';
import { analyzeImages } from '../services/analysisService';
import { OryzaApiError } from '../services/api';
import { diseaseLabel, severityLabel } from '../utils/constants';
import type { AnalysisResult } from '../types';

 
const UPLOAD_CEILING = 45;

function summarize(result: AnalysisResult): string {
  if (!result.diseases.length) {
    return (
      'Analysis complete. **No disease was detected.**\n\n' +
      'The model found no lesions above its detection thresholds. If you can ' +
      'see symptoms in the field, try a closer photo in even light.'
    );
  }

  const findings = result.diseases
    .map((d) => {
      const sci = d.scientificName ? ` (_${d.scientificName}_)` : '';
      const lesions = `${d.lesionCount} lesion${d.lesionCount === 1 ? '' : 's'}`;

      return `- **${diseaseLabel(d.name)}**${sci} — ${(d.confidence * 100).toFixed(1)}% confidence, ${lesions}, ${severityLabel(d.severity)} severity`;
    })
    .join('\n');

  const header =
    result.diseases.length > 1
      ? `Analysis complete. **${result.diseases.length} diseases** were detected on this sample:`
      : 'Analysis complete. Detected:';

  const overall =
    `\n\nOverall severity: **${severityLabel(result.overallSeverity)}** ` +
    `(${(result.overallAffectedRatio * 100).toFixed(1)}% of the image shows lesions).`;

  const coinfection =
    result.diseases.length > 1
      ? '\n\nThis is a co-infection. Each disease needs its own management, and a measure that controls one may not affect the other.'
      : '';

  const uncertain =
    result.primaryDisease && result.primaryDisease.confidence < 0.5
      ? '\n\nConfidence is low. Treat this identification as provisional and confirm it in the field before spraying.'
      : '';

  return `${header}\n\n${findings}${overall}${coinfection}${uncertain}\n\nAsk me about treatment, prevention or next steps.`;
}

export function useAnalysis() {
  const stage = useAnalysisStore((s) => s.stage);

  const run = useCallback(async () => {
    const a = useAnalysisStore.getState();
    const c = useChatStore.getState();
    if (!a.images.length) return;

    a.setError(null);
    a.setResult(null);
    a.setStage('UPLOADING');
    a.setProgress(0);

    c.addMessage({
      role: 'user',
      content: 'Here are the photos of my plants.',
      attachments: a.images.map((i) => i.previewUrl),
    });
    c.setTyping(true);

    try {
      const result = await analyzeImages(a.images, (pct) => {
        const store = useAnalysisStore.getState();
        store.setProgress(Math.round(pct * UPLOAD_CEILING));
        // The server starts work as the last bytes land.
        if (pct >= 1) store.setStage('ANALYZING');
      });

      const store = useAnalysisStore.getState();
      store.setResult(result);
      store.setStage('COMPLETED');
      store.setProgress(100);
      store.setActiveImageIndex(0);

      const chat = useChatStore.getState();
      chat.setTyping(false);
      chat.addMessage({ role: 'assistant', content: summarize(result) });

    } catch (err) {
      
      const message =
        err instanceof OryzaApiError ? err.message : 'The analysis could not be completed.';
      const store = useAnalysisStore.getState();
      store.setStage('ERROR');
      store.setProgress(0);
      store.setError(message);

      const chat = useChatStore.getState();
      chat.setTyping(false);
      // Surface the real reason. Never substitute a fabricated result.
      chat.addMessage({
        role: 'assistant',
        content: `I could not complete the analysis. ${message}`,
      });
    }
  }, []);

  return { run, stage };
}
