import type { AnalysisResult, ChatMessage, ChatResponse } from '../types';
import { api, toApiError } from './api';

export async function sendChatMessage(

  message: string,
  history: ChatMessage[],
  analysis: AnalysisResult | null
): Promise<ChatResponse> {

  try {

    const { data } = await api.post<ChatResponse>('/chat', {
      message,
      history: history.map((m) => ({ role: m.role, content: m.content })),
      analysis,
    });
    
    return data;
  } catch (err) {
    // Never answer from a canned script. Every treatment statement this app
    // makes must come from a retrieved, cited passage.
    throw toApiError(err);
  }
}
