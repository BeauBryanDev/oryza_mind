// Contracts mirror the FastAPI backend, which is the source of truth.
// Canonical YOLOv8s-seg output classes. These strings are an invariant shared
// with Weaviate metadata , python use snake_case but TS  cameCase.
export type DiseaseClass =
  | 'Bacterial_Leaf_Blight'
  | 'Brown_Spot'
  | 'Leaf_Blast'
  | 'Narrow_Brown'
  | 'Rice_Tungro'
  | 'Sheath_Blight';

export type SeverityLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

// Upload  
export interface UploadedImage {
  id: string;
  file: File;
  previewUrl: string;
  name: string;
  size: number;
}

// One disease found across the submitted photos. Several can be present at
// once: a leaf can carry more than one disease if it is rotten.
export interface DiseaseFinding {
  name: DiseaseClass;
  scientificName: string | null;
  confidence: number; // 0..1, highest single detection for this class
  lesionCount: number;
  affectedRatio: number; // lesion px / total image px
  severity: SeverityLevel;  // it depends of the affetiveRatio and  YOLO confidence
  imageIndices: number[]; // which uploads this disease appears in
}

export interface SegmentationResult {
  imageIndex: number;
  originalUrl: string; // backend sends "", client holds its own preview
  overlayUrl: string; // data:image/jpeg;base64,...
  lesionCount: number;
  affectedRatio: number;
  diseases: DiseaseClass[]; // classes present in this image
}

export interface AnalysisResult {
  diseases: DiseaseFinding[]; // empty = healthy, not an error
  primaryDisease: DiseaseFinding | null; // largest affected area
  overallAffectedRatio: number;
  overallSeverity: SeverityLevel;
  segmentations: SegmentationResult[];
  recommendations: string[] | null; // one action per item, plain text
  metadata: Record<string, unknown> | null;
}

export type PipelineStage =
  | 'IDLE'
  | 'UPLOADING'
  | 'PROCESSING'
  | 'SEGMENTING'
  | 'ANALYZING'
  | 'GENERATING_DIAGNOSIS'
  | 'COMPLETED'
  | 'ERROR';

// Chat
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string; // markdown, rendered with react-markdown
  timestamp: number;  // it v2 we will use a MongoDB  
  attachments?: string[]; // preview URLs
  loading?: boolean;
  citations?: Citation[];
}

// Provenance for a retrieved passage, so an answer traces to a page.
export interface Citation {
  chunkId: string;
  documentTitle: string;
  organization: string | null;
  pageStart: number | null;
  sourceUrl: string | null;
}

export interface ChatRequest {
  message: string;
  history: { role: 'user' | 'assistant' | 'system'; content: string }[];
  analysis: AnalysisResult | null;
}

export interface ChatResponse {
  reply: string;
  suggestions: string[] | null;
  citations: Citation[];
}

export interface HealthResponse {
  status: string; // "ok" | "degraded"
  version: string;
  modelLoaded: boolean;
  weaviateReady: boolean;
  spikeModelLoaded: boolean;
}

// Spike classifier (EfficientNetB0). A separate model with its own endpoint:
// its two classes are NOT disease classes and never reach the Weaviate filter.
export type SpikeLabel = 'HEALTHY' | 'UNHEALTHY'; // binary CNN Sigmoid output 

export interface SpikePrediction {
  imageIndex: number;
  filename: string | null;
  label: SpikeLabel;
  confidence: number; // 0..1, in the reported label
  unhealthyScore: number; // raw sigmoid, P(unhealthy)
  uncertain: boolean; // score sits near the threshold
}

export interface SpikeResult {
  predictions: SpikePrediction[];
  overallLabel: SpikeLabel; // worst case across the batch
  unhealthyCount: number;
  totalCount: number;
  modelLabel: string;
  assessment: string | null; // agent text,, null if generation failed
  recommendations: string[] | null; // one action per item, plain text
  citations: Citation[];
  grounded: boolean;
}

// Weather stays frontend-owned; there is no backend endpoint.
export interface WeatherData {
  city: string;
  temperatureC: number;
  humidityPct: number;
  rainPct: number;
  condition: string;
}

export interface ApiError {
  message: string;
  code: string | null;
}
