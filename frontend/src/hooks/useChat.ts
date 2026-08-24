import { useCallback } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useAnalysisStore } from '../stores/analysisStore';
import { sendChatMessage } from '../services/chatService';
import { OryzaApiError } from '../services/api';

export function useChat() {

  const chat = useChatStore();
  const { result } = useAnalysisStore();

  const send = useCallback(

    async (text: string) => {

      if (!result) return;

      const trimmed = text.trim();
      // Don't send empty messages.
      if (!trimmed || chat.isSending) return;

      chat.addMessage({ role: 'user', content: trimmed });
      chat.setSending(true);
      chat.setTyping(true);
      
      try {

        const res = await sendChatMessage(trimmed, chat.messages, result);

        chat.addMessage({
          role: 'assistant',
          content: res.reply,
          citations: res.citations,
        });

      } catch (err) {

        const message =
          err instanceof OryzaApiError ? err.message : 'The request could not be completed.';
        // Report the failure. Never fall back to an answer we cannot cite.
        chat.addMessage({ role: 'assistant', content: `I could not answer that. ${message}` });

      } finally {
        
        chat.setSending(false);
        chat.setTyping(false);
      }
    },
    [chat, result]
  );

  return { ...chat, send };
}
