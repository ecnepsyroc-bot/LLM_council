import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api } from './api'

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

describe('API Client', () => {
  beforeEach(() => {
    mockFetch.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('listConversations', () => {
    it('fetches conversations successfully', async () => {
      const mockConversations = [
        { id: '1', title: 'Test', message_count: 2 },
        { id: '2', title: 'Test 2', message_count: 0 },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversations),
      })

      const result = await api.listConversations()

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8001/api/conversations')
      expect(result).toEqual(mockConversations)
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(api.listConversations()).rejects.toThrow('Failed to list conversations')
    })
  })

  describe('createConversation', () => {
    it('creates conversation successfully', async () => {
      const mockConversation = { id: 'new-123', title: '', messages: [] }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversation),
      })

      const result = await api.createConversation()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        }
      )
      expect(result).toEqual(mockConversation)
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(api.createConversation()).rejects.toThrow('Failed to create conversation')
    })
  })

  describe('getConversation', () => {
    it('fetches conversation by ID', async () => {
      const mockConversation = {
        id: 'conv-123',
        title: 'Test Conversation',
        messages: [{ role: 'user', content: 'Hello' }],
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversation),
      })

      const result = await api.getConversation('conv-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations/conv-123'
      )
      expect(result).toEqual(mockConversation)
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      await expect(api.getConversation('invalid')).rejects.toThrow('Failed to get conversation')
    })
  })

  describe('sendMessage', () => {
    it('sends message successfully', async () => {
      const mockResponse = {
        user_message: { role: 'user', content: 'Hello' },
        assistant_message: { role: 'assistant', stage3: { response: 'Hi!' } },
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await api.sendMessage('conv-123', 'Hello')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations/conv-123/message',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: 'Hello', images: [] }),
        }
      )
      expect(result).toEqual(mockResponse)
    })

    it('sends message with images', async () => {
      const mockResponse = { user_message: {}, assistant_message: {} }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      await api.sendMessage('conv-123', 'Describe this', ['base64data'])

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations/conv-123/message',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: 'Describe this', images: ['base64data'] }),
        }
      )
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(api.sendMessage('conv-123', 'Hello')).rejects.toThrow('Failed to send message')
    })
  })

  describe('getConfig', () => {
    it('fetches config successfully', async () => {
      const mockConfig = {
        council_models: ['model1', 'model2'],
        chairman_model: 'model1',
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConfig),
      })

      const result = await api.getConfig()

      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8001/api/config')
      expect(result).toEqual(mockConfig)
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(api.getConfig()).rejects.toThrow('Failed to get config')
    })
  })

  describe('deleteConversation', () => {
    it('deletes conversation successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      })

      await api.deleteConversation('conv-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations/conv-123',
        { method: 'DELETE' }
      )
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      await expect(api.deleteConversation('invalid')).rejects.toThrow('Failed to delete conversation')
    })
  })

  describe('updateConversation', () => {
    it('updates conversation title', async () => {
      const mockConversation = {
        id: 'conv-123',
        title: 'New Title',
        is_pinned: false,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversation),
      })

      const result = await api.updateConversation('conv-123', { title: 'New Title' })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations/conv-123',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: 'New Title' }),
        }
      )
      expect(result).toEqual(mockConversation)
    })

    it('updates conversation pin status', async () => {
      const mockConversation = {
        id: 'conv-123',
        title: 'Test',
        is_pinned: true,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversation),
      })

      const result = await api.updateConversation('conv-123', { is_pinned: true })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/api/conversations/conv-123',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_pinned: true }),
        }
      )
      expect(result.is_pinned).toBe(true)
    })

    it('throws error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
      })

      await expect(api.updateConversation('conv-123', {})).rejects.toThrow('Failed to update conversation')
    })
  })

  describe('sendMessageStream', () => {
    it('processes SSE events correctly', async () => {
      const events: Array<{ type: string; data: unknown }> = []

      // Create a mock readable stream
      const sseData = [
        'data: {"type":"stage1_start","message":"Starting"}\n\n',
        'data: {"type":"stage1_complete","responses":[]}\n\n',
        'data: {"type":"complete","result":{}}\n\n',
      ].join('')

      const encoder = new TextEncoder()
      const mockReader = {
        read: vi
          .fn()
          .mockResolvedValueOnce({ done: false, value: encoder.encode(sseData) })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      })

      await api.sendMessageStream('conv-123', 'Hello', (type, event) => {
        events.push({ type, data: event })
      })

      expect(events).toHaveLength(3)
      expect(events[0].type).toBe('stage1_start')
      expect(events[1].type).toBe('stage1_complete')
      expect(events[2].type).toBe('complete')
    })

    it('throws error when response not ok', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      await expect(
        api.sendMessageStream('conv-123', 'Hello', () => {})
      ).rejects.toThrow('Failed to send message')
    })

    it('throws error when no response body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      })

      await expect(
        api.sendMessageStream('conv-123', 'Hello', () => {})
      ).rejects.toThrow('No response body')
    })
  })
})
