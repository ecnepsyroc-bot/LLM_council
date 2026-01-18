/**
 * API client for the LLM Council backend.
 */

import type { Conversation, StreamEvent, StreamEventType, DeliberationOptions } from './types';

// Use environment variable for API base URL, defaulting to relative path for production
// In development: set VITE_API_BASE=http://localhost:8001
// In production: leave empty to use same origin (served via reverse proxy)
const API_BASE = import.meta.env.VITE_API_BASE || '';

export const api = {
  /**
   * List all conversations.
   */
  async listConversations(): Promise<Conversation[]> {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation(): Promise<Conversation> {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId: string): Promise<Conversation> {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation (non-streaming).
   */
  async sendMessage(conversationId: string, content: string, images: string[] = []): Promise<unknown> {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, images }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   */
  async sendMessageStream(
    conversationId: string,
    content: string,
    onEvent: (eventType: StreamEventType, event: StreamEvent) => void,
    images: string[] = [],
    options?: DeliberationOptions
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, images, options }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data) as StreamEvent;
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
  /**
   * Get council configuration.
   */
  async getConfig(): Promise<{ council_models: string[]; chairman_model: string }> {
    const response = await fetch(`${API_BASE}/api/config`);
    if (!response.ok) {
      throw new Error('Failed to get config');
    }
    return response.json();
  },

  /**
   * Delete a conversation.
   */
  async deleteConversation(conversationId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
  },

  async updateConversation(conversationId: string, updates: { title?: string; is_pinned?: boolean; is_hidden?: boolean }): Promise<Conversation> {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!response.ok) {
      throw new Error('Failed to update conversation');
    }
    return response.json();
  },
};
