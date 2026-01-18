// Core model types
export interface Model {
  id: string;
  name: string;
  avatarUrl?: string;
}

export interface ModelResponse {
  model: string;
  response: string;
  confidence?: number | null;  // 1-10 confidence score
  responseTime?: number;
  tokenCount?: number;
  isStreaming?: boolean;
  streamingContent?: string;  // Accumulated content during streaming
  // Self-MoA fields
  base_model?: string;
  sample_id?: number;
}

export interface PeerEvaluation {
  model: string;
  ranking: string;
  parsed_ranking: string[];
  debate_round?: number;  // For multi-round debate
  rubric_scores?: RubricScores;  // For rubric-based evaluation
}

// Rubric evaluation types
export interface RubricScores {
  [responseLabel: string]: {
    accuracy?: number;
    completeness?: number;
    clarity?: number;
    reasoning?: number;
    practicality?: number;
  };
}

// Advanced ranking types (Borda, MRR, Confidence-weighted)
export interface AggregateRanking {
  model: string;
  average_rank: number;
  rankings_count: number;
  // Borda count fields
  borda_score?: number;
  normalized_score?: number;
  // MRR fields
  mrr_score?: number;
  reciprocal_sum?: number;
  // Confidence-weighted fields
  weighted_score?: number;
  raw_score?: number;
  confidence_boost?: number;
}

export interface Consensus {
  has_consensus: boolean;
  agreement_score: number;  // 0.0 to 1.0
  top_model: string | null;
  top_votes: number;
  total_voters: number;
  early_exit_eligible?: boolean;  // For DOWN pattern
}

// Stage 1 consensus (early exit based on confidence)
export interface Stage1Consensus {
  early_exit_possible: boolean;
  high_confidence_model: string | null;
  top_confidence?: number;
  avg_other_confidence?: number;
  reason: string;
}

// Meta-evaluation for chairman synthesis
export interface MetaEvaluation {
  model: string;
  evaluation: string;
}

// Extended synthesis with optional meta-evaluation
export interface SynthesisWithMeta {
  synthesis: {
    model: string;
    response: string;
  };
  meta_evaluation?: MetaEvaluation;
}

// Feature flags for deliberation
export interface DeliberationFeatures {
  use_rubric: boolean;
  debate_rounds: number;
  early_exit_used: boolean;
  use_self_moa: boolean;
  rotating_chairman: boolean;
  meta_evaluate: boolean;
  chairman_model: string;
}

export type VotingMethod = "simple" | "borda" | "mrr" | "confidence_weighted";

export interface Metadata {
  label_to_model: Record<string, string>;
  aggregate_rankings: AggregateRanking[];
  consensus?: Consensus;
  // New advanced metadata
  voting_method?: VotingMethod;
  features?: DeliberationFeatures;
  stage1_consensus?: Stage1Consensus;
  debate_history?: PeerEvaluation[][];  // Array of rounds
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
  role: "user";
  content: string;
  images?: string[];
}

export interface AssistantMessage {
  role: "assistant";
  stage1: ModelResponse[] | null;
  stage2: PeerEvaluation[] | null;
  stage3: ModelResponse | SynthesisWithMeta | null;
  metadata: Metadata | null;
  loading: {
    stage1: boolean;
    stage2: boolean;
    stage3: boolean;
  };
  // Per-model streaming state
  streamingResponses?: Record<string, {
    content: string;
    isStreaming: boolean;
    isDone: boolean;
  }>;
}

export type Message = UserMessage | AssistantMessage;

// Conversation types
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
  is_pinned?: boolean;
  is_hidden?: boolean;
  messages?: Message[];
}

// Council status types
export type ModelStatus =
  | "idle"
  | "thinking"
  | "responding"
  | "evaluating"
  | "finished"
  | "error";

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
  showHidden: boolean;

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

  // Config
  config: CouncilConfig | null;
  fetchConfig: () => Promise<void>;

  // Actions
  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (id: string | null) => void;
  updateConversation: (conversation: Conversation) => void;
  deleteConversation: (id: string) => Promise<void>;
  togglePin: (id: string) => Promise<void>;
  toggleHide: (id: string) => Promise<void>;
  toggleShowHidden: () => void;
  addMessage: (message: Message) => void;
  updateLastMessage: (updates: Partial<AssistantMessage> | ((prev: AssistantMessage) => Partial<AssistantMessage>)) => void;
  setStage: (stage: 0 | 1 | 2 | 3) => void;
  setModelStatus: (modelId: string, status: CouncilMemberStatus) => void;
  resetDeliberation: () => void;
  toggleSidebar: () => void;
  toggleStatusPanel: () => void;
  setLoading: (loading: boolean) => void;
}

// Streaming event types
export type StreamEventType =
  | "stage1_start"
  | "stage1_complete"
  | "stage2_start"
  | "stage2_complete"
  | "stage3_start"
  | "stage3_complete"
  | "title_complete"
  | "complete"
  | "error"
  // New streaming events for per-model updates
  | "model_start"
  | "model_chunk"
  | "model_done"
  | "model_error";

export interface StreamEvent {
  type: StreamEventType;
  data?: ModelResponse[] | PeerEvaluation[] | ModelResponse | SynthesisWithMeta;
  metadata?: Metadata;
  message?: string;
  title?: string;
  // Per-model streaming fields
  model?: string;
  content?: string;
  accumulated?: string;
  response?: ModelResponse;
  error?: string;
}

export interface CouncilConfig {
  council_models: string[];
  chairman_model: string;
}

// Deliberation options for API calls
export interface DeliberationOptions {
  voting_method?: VotingMethod;
  use_rubric?: boolean;
  debate_rounds?: number;
  enable_early_exit?: boolean;
  use_self_moa?: boolean;
  rotating_chairman?: boolean;
  meta_evaluate?: boolean;
}

// UI Preferences
export type ThemeMode = "light" | "dark" | "system";
export type FontFamily = "default" | "dyslexic" | "mono";
export type FontSize = "small" | "medium" | "large" | "xlarge";
export type Stage1Layout = "stacked" | "grid" | "tabs";
export type ColorScheme = "default" | "high-contrast" | "colorblind-safe";

export interface UIPreferences {
  // Theme & Appearance
  theme: ThemeMode;
  colorScheme: ColorScheme;
  fontFamily: FontFamily;
  fontSize: FontSize;

  // Layout
  stage1Layout: Stage1Layout;
  compactMode: boolean;
  showTimestamps: boolean;

  // Accessibility
  reduceMotion: boolean;
  highContrast: boolean;

  // Features
  showConfidenceBadges: boolean;
  showRubricScores: boolean;
  autoExpandResponses: boolean;
  enableCodePreview: boolean;
}

export interface CouncilSettings {
  // Voting & Ranking
  votingMethod: VotingMethod;

  // Deliberation Features
  useRubric: boolean;
  debateRounds: number;
  enableEarlyExit: boolean;
  useSelfMoA: boolean;
  rotatingChairman: boolean;
  metaEvaluate: boolean;

  // Self-MoA specific
  selfMoaModel: string | null;
  selfMoaSamples: number;
}

export const DEFAULT_UI_PREFERENCES: UIPreferences = {
  theme: "dark",
  colorScheme: "default",
  fontFamily: "default",
  fontSize: "medium",
  stage1Layout: "stacked",
  compactMode: false,
  showTimestamps: true,
  reduceMotion: false,
  highContrast: false,
  showConfidenceBadges: true,
  showRubricScores: true,
  autoExpandResponses: true,
  enableCodePreview: true,
};

export const DEFAULT_COUNCIL_SETTINGS: CouncilSettings = {
  votingMethod: "borda",
  useRubric: false,
  debateRounds: 1,
  enableEarlyExit: true,
  useSelfMoA: false,
  rotatingChairman: false,
  metaEvaluate: false,
  selfMoaModel: null,
  selfMoaSamples: 5,
};
