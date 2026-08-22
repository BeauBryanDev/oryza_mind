import { ACCEPTED_FORMATS, MAX_FILE_SIZE_MB, MAX_IMAGES } from './constants';

export interface ValidationResult {
  ok: boolean;
  message?: string;
}

export function validateFile(file: File): ValidationResult {
  
  if (!ACCEPTED_FORMATS.includes(file.type)) {

    return { ok: false, message: `Unsupported format: ${file.name}` };
  }
  const mb = file.size / (1024 * 1024);

  if (mb > MAX_FILE_SIZE_MB) {

    return { ok: false, message: `${file.name} is larger than ${MAX_FILE_SIZE_MB} MB` };
  }

  return { ok: true };
}

// `limit` is a parameter because the spike drop zone has its own quota; both
// still mirror the backend, which rejects an extra file rather than ignoring it.
export function validateBatch(
  current: number,
  incoming: File[],
  limit: number = MAX_IMAGES
): ValidationResult {

  if (current + incoming.length > limit) {

    return { ok: false, message: `Up to ${limit} images allowed` };
  }

  for (const f of incoming) {

    const r = validateFile(f);

    if (!r.ok) return r;
  }

  return { ok: true };
}
