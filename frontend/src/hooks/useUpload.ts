import { useCallback, useState } from 'react';
import { useAnalysisStore } from '../stores/analysisStore';
import { validateBatch } from '../utils/validators';
import { makeId, makePreviewUrl } from '../utils/imageUtils';
import type { UploadedImage } from '../types';

export function useUpload() {

  const { images, addImages, removeImage, clearImages } = useAnalysisStore();
  const [error, setError] = useState<string | null>(null);

  const handleFiles = useCallback(

    (fileList: FileList | File[]) => {

      const arr = Array.from(fileList);
      const result = validateBatch(images.length, arr);

      if (!result.ok) {

        setError(result.message ?? 'Invalid file');
        setTimeout(() => setError(null), 3500);
        return;
      }

      setError(null);

      const mapped: UploadedImage[] = arr.map((file) => ({

        id: makeId(),
        file,
        previewUrl: makePreviewUrl(file),
        name: file.name,
        size: file.size,
      }));

      addImages(mapped);
    },
    [images.length, addImages]
  );

  return { images, error, handleFiles, removeImage, clearImages };
  
}
