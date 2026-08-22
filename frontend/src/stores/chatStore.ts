import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { ChatMessage } from '../types';
import { makeId } from '../utils/imageUtils';

interface ChatState {

  messages: ChatMessage[];
  isSending: boolean;
  isTyping: boolean;
  addMessage: (m: Omit<ChatMessage, 'id' | 'timestamp'> & { id?: string; timestamp?: number }) => string;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  setSending: (v: boolean) => void;
  setTyping: (v: boolean) => void;
  reset: () => void;
}

const STORAGE_KEY = 'oryza-chat';
// localStorage is ~5 MB and citations make each turn sizeable. Old turns are
// dropped rather than letting a write fail and lose the whole thread.
const MAX_PERSISTED_MESSAGES = 60;

export const useChatStore = create<ChatState>()(

  persist(

    (set, get) => ({

      messages: [],
      isSending: false,
      isTyping: false,

      addMessage: (m) => {

        const id = m.id ?? makeId();

        const msg: ChatMessage = {

          id,
          timestamp: m.timestamp ?? Date.now(),
          role: m.role,
          content: m.content,
          attachments: m.attachments,
          loading: m.loading,
          citations: m.citations,
        };

        set({ messages: [...get().messages, msg] });
        return id;

      },
      updateMessage: (id, patch) =>
        set({ messages: get().messages.map((m) => (m.id === id ? { ...m, ...patch } : m)) }),
      setSending: (isSending) => set({ isSending }),
      setTyping: (isTyping) => set({ isTyping }),
      reset: () => set({ messages: [], isSending: false, isTyping: false }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      version: 1,
      partialize: (state) => ({
        
        messages: state.messages.slice(-MAX_PERSISTED_MESSAGES).map((m) => ({
          ...m,
          // attachments are blob: URLs from URL.createObjectURL. They die with
          // the document, so persisting them would restore broken thumbnails.
          attachments: undefined,
          loading: undefined,
        })),
      }),
      onRehydrateStorage: () => (state) => {
        // isSending/isTyping are never persisted: a refresh mid-request would
        // otherwise restore a thread stuck showing the typing indicator.
        state?.setSending(false);
        state?.setTyping(false);
      },
    }
  )
);
