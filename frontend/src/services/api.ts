import axios, { AxiosError } from 'axios';
import type { ApiError } from '../types';
import { API_BASE_URL } from '../utils/constants'; // backend port is 8005

export const api = axios.create({
    //  axios.create()  is a factory function that returns a new instance of axios
  baseURL: API_BASE_URL,  // CORS is handled by the reverse proxy fastapi
  timeout: 30000,
  headers: { Accept: 'application/json' },
});

// /analyze runs vision, retrieval and one LLM call, and pays a one-off model
// load on the first request. 30s is not enough for a cold start.
export const ANALYZE_TIMEOUT_MS = 120000;
// TODO: THERE IS AN ANNNOYING DELAY ISSUE HERE I MUST FIX ASAP 
export class OryzaApiError extends Error {
  code: string | null;
  status: number | null;

  constructor(message: string, code: string | null = null, status: number | null = null) {
    super(message);
    this.name = 'OryzaApiError';
    this.code = code;
    this.status = status;
  }
}

// The backend returns {message, code} for every deliberate failure. Anything
// else is a transport problem and gets a generic message 
export function toApiError(err: unknown): OryzaApiError {

  const ax = err as AxiosError<ApiError>;
  const data = ax?.response?.data;

  if (data?.message) {
    return new OryzaApiError(data.message, data.code ?? null, ax.response?.status ?? null);
  }
  if (ax?.code === 'ECONNABORTED') {
    return new OryzaApiError('The request timed out. The server may be starting up.', 'timeout');
  }
  if (!ax?.response) {
    return new OryzaApiError('Cannot reach the OryzaMind server.', 'network_error');
  }
  return new OryzaApiError('Something went wrong on the server.', 'internal_error', ax.response.status);
}
