// Core model types
export interface Model {
  id: string;
  name: string;
  avatarUrl?: string;
}

export interface ModelResponse {
  model: string;
  response: string;
  responseTime?: number;
  tokenCount?: number;
  isStreaming?: boolean;
}

export interface PeerEvaluation {
  model: string;
  ranking: string;
  parsed_ranking: string[];
}

export interface AggregateRanking {
  model: string;
  average_rank: number;
  rankings_count: number;
}

export interface Metadata {
  label_to_model: Record<string, string>;
  aggregate_rankings: AggregateRanking[];
}

export interface Synthesis {
  model: string;
  response: string;
}

// Deliberation types
export interface DeliberationTurn {
  id: string;
  prompt: string;
  stage1Responses: ModelResponse[];
  stage2Rankings: PeerEvaluation[];
  stage3Synthesis: Synthesis | null;
  metadata: Metadata | null;
  timestamp: string;
  cost?: number;
}

// Message types
export interface UserMessage {
  role: 'user';
  content: string;
}

export interface AssistantMessage {
  role: 'assistant';
  stage1: ModelResponse[] | null;
  stage2: PeerEvaluation[] | null;
  stage3: ModelResponse | null;
  metadata: Metadata | null;
  loading: {
    stage1: boolean;
    stage2: boolean;
    stage3: boolean;
  };
}

export type Message = UserMessage | AssistantMessage;

// Conversation types
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
  messages?: Message[];
}

// Council status types
export type ModelStatus = 'idle' | 'thinking' | 'responding' | 'evaluating' | 'finished' | 'error';

export interface CouncilMemberStatus {
  modelId: string;
  modelName: string;
  status: ModelStatus;
  currentStage?: 1 | 2 | 3;
}

// Zustand store types
export interface CouncilState {
  // Conversations
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversation: Conversation | null;

  // Deliberation state
  deliberation: {
    stage: 0 | 1 | 2 | 3; // 0 = idle
    responses: ModelResponse[];
    rankings: PeerEvaluation[];
    synthesis: Synthesis | null;
  };

  // Council member statuses
  councilStatus: Record<string, CouncilMemberStatus>;

  // UI state
  isLoading: boolean;
  sidebarCollapsed: boolean;
  statusPanelCollapsed: boolean;

  // Actions
  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (id: string | null) => void;
  updateConversation: (conversation: Conversation) => void;
  addMessage: (message: Message) => void;
  updateLastMessage: (updates: Partial<AssistantMessage>) => void;
  setStage: (stage: 0 | 1 | 2 | 3) => void;
  setModelStatus: (modelId: string, status: CouncilMemberStatus) => void;
  resetDeliberation: () => void;
  toggleSidebar: () => void;
  toggleStatusPanel: () => void;
  setLoading: (loading: boolean) => void;
}

// Streaming event types
export type StreamEventType =
  | 'stage1_start'
  | 'stage1_complete'
  | 'stage2_start'
  | 'stage2_complete'
  | 'stage3_start'
  | 'stage3_complete'
  | 'title_complete'
  | 'complete'
  | 'error';

export interface StreamEvent {
  type: StreamEventType;
  data?: ModelResponse[] | PeerEvaluation[] | ModelResponse;
  metadata?: Metadata;
  message?: string;
  title?: string;
}
