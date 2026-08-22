import type { DiseaseClass, SeverityLevel } from '../types';

export const MAX_IMAGES = 3;
export const MAX_FILE_SIZE_MB = 8;
export const ACCEPTED_FORMATS = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

export const API_BASE_URL =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8005';

export const APP_NAME = 'OryzaMind';
// Display form for the header wordmark.
export const APP_BRAND = 'ORYZA-MIND';
export const APP_TAGLINE = 'AI AGENT FOR RICE DISEASE DETECTION'; // it is not an agent yet.  
export const APP_VERSION = 'v1.0.0';
export const VISION_MODEL_LABEL = 'YOLOv8s-SEG';
export const SPIKE_MODEL_LABEL = 'EFFICIENTNET-B0';
// Matches MAX_IMAGES in app/services/spike_service.py.
export const MAX_SPIKE_IMAGES = 3;
// these is my color palette , I  like it for thia Agriculture SPA 
export const DISEASE_COLORS = ['#8CFF4D', '#C7F000', '#39FF70', '#4FA65B', '#2E7A3A'];

// Presentation only. The canonical class string stays the identifier in state,
export const DISEASE_LABELS: Record<DiseaseClass, string> = {  
  Bacterial_Leaf_Blight: 'Bacterial Leaf Blight',
  Brown_Spot: 'Brown Spot',
  Leaf_Blast: 'Leaf Blast',
  Narrow_Brown: 'Narrow Brown Leaf Spot',
  Rice_Tungro: 'Rice Tungro',
  Sheath_Blight: 'Sheath Blight',
};

export const SEVERITY_LABELS: Record<SeverityLevel, string> = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  CRITICAL: 'Critical',
};

// Stable colour per class, so a disease keeps its colour across panels.
export const DISEASE_COLOR_BY_CLASS: Record<DiseaseClass, string> = {
  Bacterial_Leaf_Blight: '#8CFF4D', // it came as TS Interface
  Brown_Spot: '#C7F000',
  Leaf_Blast: '#39FF70',
  Narrow_Brown: '#4FA65B',
  Rice_Tungro: '#2E7A3A',
  Sheath_Blight: '#6FE3A1',
};

export function diseaseLabel(name: string): string {
  return DISEASE_LABELS[name as DiseaseClass] ?? name.replace(/_/g, ' ');
}

export function severityLabel(level: SeverityLevel): string {
  return SEVERITY_LABELS[level] ?? level;
}
