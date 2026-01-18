import { create } from 'zustand';
import { api } from '../api';
import type {
  Conversation,
  Message,
  AssistantMessage,
  ModelResponse,
  PeerEvaluation,
  Synthesis,
  CouncilMemberStatus,
  CouncilState,
} from '../types';

const initialDeliberation = {
  stage: 0 as const,
  responses: [] as ModelResponse[],
  rankings: [] as PeerEvaluation[],
  synthesis: null as Synthesis | null,
};

export const useCouncilStore = create<CouncilState>((set, get) => ({
  // Initial state
  conversations: [],
  activeConversationId: null,
  activeConversation: null,
  showHidden: false,
  deliberation: initialDeliberation,
  councilStatus: {},
  isLoading: false,
  sidebarCollapsed: false,
  statusPanelCollapsed: false,

  // Config
  config: null,
  fetchConfig: async () => {
    try {
      const config = await api.getConfig();
      set({ config });
    } catch (error) {
      console.error('Failed to fetch config:', error);
    }
  },

  // Actions
  setConversations: (conversations: Conversation[]) => {
    set({ conversations });
  },

  setActiveConversation: (id: string | null) => {
    set({
      activeConversationId: id,
      activeConversation: id
        ? get().conversations.find(c => c.id === id) || null
        : null,
    });
  },

  updateConversation: (conversation: Conversation) => {
    set(state => ({
      conversations: state.conversations.map(c =>
        c.id === conversation.id ? conversation : c
      ),
      activeConversation: state.activeConversationId === conversation.id
        ? conversation
        : state.activeConversation,
    }));
  },

  deleteConversation: async (id: string) => {
    try {
      await api.deleteConversation(id);
      set(state => ({
        conversations: state.conversations.filter(c => c.id !== id),
        activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
        activeConversation: state.activeConversationId === id ? null : state.activeConversation,
      }));
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  },

  togglePin: async (id: string) => {
    const conversation = get().conversations.find(c => c.id === id);
    if (!conversation) return;

    try {
      const updated = await api.updateConversation(id, { is_pinned: !conversation.is_pinned });
      set(state => ({
        conversations: state.conversations.map(c => c.id === id ? updated : c)
      }));
    } catch (error) {
      console.error('Failed to toggle pin:', error);
    }
  },

  toggleHide: async (id: string) => {
    const conversation = get().conversations.find(c => c.id === id);
    if (!conversation) return;

    try {
      const updated = await api.updateConversation(id, { is_hidden: !conversation.is_hidden });
      set(state => ({
        conversations: state.conversations.map(c => c.id === id ? updated : c)
      }));
    } catch (error) {
      console.error('Failed to toggle hide:', error);
    }
  },

  toggleShowHidden: () => {
    set(state => ({ showHidden: !state.showHidden }));
  },

  addMessage: (message: Message) => {
    set(state => {
      if (!state.activeConversation) return state;

      const updatedConversation = {
        ...state.activeConversation,
        messages: [...(state.activeConversation.messages || []), message],
      };

      return {
        activeConversation: updatedConversation,
        conversations: state.conversations.map(c =>
          c.id === updatedConversation.id ? updatedConversation : c
        ),
      };
    });
  },

  updateLastMessage: (updates: Partial<AssistantMessage> | ((prev: AssistantMessage) => Partial<AssistantMessage>)) => {
    set(state => {
      if (!state.activeConversation?.messages?.length) return state;

      const messages = [...state.activeConversation.messages];
      const lastIndex = messages.length - 1;
      const lastMessage = messages[lastIndex];

      if (lastMessage?.role !== 'assistant') return state;

      // Support both object and function updates
      const resolvedUpdates = typeof updates === 'function'
        ? updates(lastMessage as AssistantMessage)
        : updates;

      messages[lastIndex] = { ...lastMessage, ...resolvedUpdates } as AssistantMessage;

      const updatedConversation = {
        ...state.activeConversation,
        messages,
      };

      return {
        activeConversation: updatedConversation,
        conversations: state.conversations.map(c =>
          c.id === updatedConversation.id ? updatedConversation : c
        ),
      };
    });
  },

  setStage: (stage: 0 | 1 | 2 | 3) => {
    set(state => ({
      deliberation: { ...state.deliberation, stage },
    }));
  },

  setModelStatus: (modelId: string, status: CouncilMemberStatus) => {
    set(state => ({
      councilStatus: { ...state.councilStatus, [modelId]: status },
    }));
  },

  resetDeliberation: () => {
    set({
      deliberation: initialDeliberation,
      councilStatus: {},
    });
  },

  toggleSidebar: () => {
    set(state => ({ sidebarCollapsed: !state.sidebarCollapsed }));
  },

  toggleStatusPanel: () => {
    set(state => ({ statusPanelCollapsed: !state.statusPanelCollapsed }));
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },
}));
