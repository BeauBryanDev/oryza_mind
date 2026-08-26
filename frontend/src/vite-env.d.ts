/// <reference types="vite/client" />
// backend use port 8005 by default hence VITE_API_BASE_URL is 8005
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
