import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Bot, Loader2, CheckCircle, Sparkles, Award, BarChart3, Zap, MessageSquare, Settings } from 'lucide-react';
import { MarkdownRenderer } from '../shared/MarkdownRenderer';
import { useCouncilStore } from '../../store/councilStore';
import { useSettingsStore } from '../../store/settingsStore';
import { InputComposer } from '../shared/InputComposer';
import { SidebarToggle } from './ConversationSidebar';
import { StatusPanelToggle } from './CouncilStatusPanel';
import { api } from '../../api';
import type { Message, AssistantMessage, ModelResponse, PeerEvaluation, Consensus, Metadata, AggregateRanking, SynthesisWithMeta, VotingMethod } from '../../types';

// Settings button toggle
function SettingsToggle() {
  const { openSettings } = useSettingsStore();

  return (
    <motion.button
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      onClick={openSettings}
      className="fixed right-14 top-4 z-50 p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
      title="Open settings"
    >
      <Settings size={18} />
    </motion.button>
  );
}

// Voting Method Badge
function VotingMethodBadge({ method }: { method?: VotingMethod }) {
  if (!method) return null;

  const labels: Record<VotingMethod, { label: string; color: string }> = {
    simple: { label: 'Simple Avg', color: 'bg-gray-600' },
    borda: { label: 'Borda Count', color: 'bg-purple-600' },
    mrr: { label: 'MRR', color: 'bg-blue-600' },
    confidence_weighted: { label: 'Confidence Weighted', color: 'bg-green-600' }
  };

  const { label, color } = labels[method] || { label: method, color: 'bg-gray-600' };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${color}`}>
      {label}
    </span>
  );
}

// Feature badges for active features
function FeatureBadges({ metadata }: { metadata: Metadata | null | undefined }) {
  if (!metadata?.features) return null;

  const { features } = metadata;
  const badges = [];

  if (features.use_rubric) {
    badges.push({ label: 'Rubric', icon: BarChart3, color: 'text-yellow-400' });
  }
  if (features.debate_rounds > 1) {
    badges.push({ label: `${features.debate_rounds} Rounds`, icon: MessageSquare, color: 'text-blue-400' });
  }
  if (features.early_exit_used) {
    badges.push({ label: 'Early Exit', icon: Zap, color: 'text-green-400' });
  }
  if (features.use_self_moa) {
    badges.push({ label: 'Self-MoA', icon: Bot, color: 'text-purple-400' });
  }
  if (features.rotating_chairman) {
    badges.push({ label: 'Rotating Chair', icon: Award, color: 'text-orange-400' });
  }

  if (badges.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-3">
      {badges.map(({ label, icon: Icon, color }) => (
        <span key={label} className={`inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800 rounded text-xs ${color}`}>
          <Icon size={10} />
          {label}
        </span>
      ))}
    </div>
  );
}

// Confidence Badge Component
function ConfidenceBadge({ confidence }: { confidence: number | null | undefined }) {
  if (confidence === null || confidence === undefined) return null;

  let colorClass = 'bg-gray-600 text-gray-200';
  if (confidence >= 8) {
    colorClass = 'bg-green-600 text-green-100';
  } else if (confidence >= 6) {
    colorClass = 'bg-blue-600 text-blue-100';
  } else if (confidence >= 4) {
    colorClass = 'bg-yellow-600 text-yellow-100';
  } else {
    colorClass = 'bg-red-600 text-red-100';
  }

  return (
    <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-medium ${colorClass}`} title={`Confidence: ${confidence}/10`}>
      {confidence}/10
    </span>
  );
}

// Streaming indicator for a model
function StreamingIndicator() {
  return (
    <span className="inline-flex items-center gap-1 text-blue-400 text-sm">
      <Loader2 size={12} className="animate-spin" />
      <span className="animate-pulse">typing...</span>
    </span>
  );
}

// Stage 1: Individual Responses with Layout Options
function Stage1View({
  responses,
  streamingResponses
}: {
  responses: ModelResponse[];
  streamingResponses?: Record<string, { content: string; isStreaming: boolean; isDone: boolean }>;
}) {
  const { uiPreferences } = useSettingsStore();
  const [activeTab, setActiveTab] = useState(0);

  const allModels = new Set<string>();
  responses?.forEach(r => allModels.add(r.model));
  if (streamingResponses) {
    Object.keys(streamingResponses).forEach(m => allModels.add(m));
  }

  if (allModels.size === 0) return null;

  const modelList = Array.from(allModels);

  // Response card component
  const ResponseCard = ({ model, idx, isCompact = false }: { model: string; idx: number; isCompact?: boolean }) => {
    const completedResponse = responses?.find(r => r.model === model);
    const streamingState = streamingResponses?.[model];

    // Handle Self-MoA naming
    let displayName = model.split('/').pop() || model;
    if (completedResponse?.sample_id !== undefined) {
      displayName = `${completedResponse.base_model?.split('/').pop() || displayName} #${completedResponse.sample_id + 1}`;
    }

    const content = completedResponse?.response || streamingState?.content || '';
    const confidence = completedResponse?.confidence;
    const isStreaming = streamingState?.isStreaming && !completedResponse;
    const isDone = completedResponse || streamingState?.isDone;

    return (
      <motion.div
        key={model}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: idx * 0.05 }}
        className={`bg-gray-800/50 border rounded-lg overflow-hidden flex flex-col ${
          isStreaming ? 'border-blue-500/50' : 'border-gray-700'
        } ${isCompact ? 'h-full' : ''}`}
      >
        <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2 shrink-0">
          <Bot size={14} className={isStreaming ? 'text-blue-400' : 'text-gray-500'} />
          <span className="text-sm font-medium text-gray-300 truncate">{displayName}</span>
          {uiPreferences.showConfidenceBadges && <ConfidenceBadge confidence={confidence} />}
          {isStreaming && <StreamingIndicator />}
          {isDone && !isStreaming && (
            <CheckCircle size={14} className="text-green-500 ml-auto shrink-0" />
          )}
        </div>
        <div className={`p-4 prose prose-invert prose-sm max-w-none flex-1 ${isCompact ? 'overflow-y-auto max-h-80' : ''}`}>
          {content ? (
            <MarkdownRenderer content={content} />
          ) : (
            <span className="text-gray-500 italic">Waiting for response...</span>
          )}
        </div>
      </motion.div>
    );
  };

  // Tabs layout
  if (uiPreferences.stage1Layout === 'tabs') {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">
          Stage 1: Individual Responses
        </h3>
        {/* Tab headers */}
        <div className="flex gap-1 overflow-x-auto pb-2 scrollbar-thin">
          {modelList.map((model, idx) => {
            const completedResponse = responses?.find(r => r.model === model);
            const streamingState = streamingResponses?.[model];
            let displayName = model.split('/').pop() || model;
            if (completedResponse?.sample_id !== undefined) {
              displayName = `${completedResponse.base_model?.split('/').pop() || displayName} #${completedResponse.sample_id + 1}`;
            }
            const isStreaming = streamingState?.isStreaming && !completedResponse;
            const isDone = completedResponse || streamingState?.isDone;

            return (
              <button
                type="button"
                key={model}
                onClick={() => setActiveTab(idx)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors shrink-0 ${
                  activeTab === idx
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                }`}
              >
                {isStreaming ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : isDone ? (
                  <CheckCircle size={12} className="text-green-400" />
                ) : (
                  <Bot size={12} />
                )}
                <span className="truncate max-w-[120px]">{displayName}</span>
              </button>
            );
          })}
        </div>
        {/* Active tab content */}
        {modelList[activeTab] && (
          <ResponseCard model={modelList[activeTab]} idx={0} />
        )}
      </div>
    );
  }

  // Grid layout (side-by-side)
  if (uiPreferences.stage1Layout === 'grid') {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">
          Stage 1: Individual Responses
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {modelList.map((model, idx) => (
            <ResponseCard key={model} model={model} idx={idx} isCompact />
          ))}
        </div>
      </div>
    );
  }

  // Default: Stacked layout
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">
        Stage 1: Individual Responses
      </h3>
      <div className="grid gap-3">
        {modelList.map((model, idx) => (
          <ResponseCard key={model} model={model} idx={idx} />
        ))}
      </div>
    </div>
  );
}

// Consensus indicator component
function ConsensusIndicator({ consensus }: { consensus: Consensus | undefined }) {
  if (!consensus) return null;

  const topModelName = consensus.top_model?.split('/').pop() || consensus.top_model;
  const agreementPercent = Math.round(consensus.agreement_score * 100);

  if (consensus.has_consensus) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-green-900/30 border border-green-600/50 rounded-lg p-3 mb-4 flex items-center gap-3"
      >
        <Sparkles size={20} className="text-green-400" />
        <div>
          <div className="text-sm font-medium text-green-300">Full Consensus Achieved</div>
          <div className="text-xs text-green-400/80">
            All {consensus.total_voters} models agree: <span className="font-semibold">{topModelName}</span> provided the best response
          </div>
        </div>
        {consensus.early_exit_eligible && (
          <span className="ml-auto px-2 py-0.5 bg-green-600/30 rounded text-xs text-green-300">
            Early Exit Eligible
          </span>
        )}
      </motion.div>
    );
  }

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 mb-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400">Agreement Level</span>
        <span className="text-sm font-medium text-gray-200">{agreementPercent}%</span>
      </div>
      <div className="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${agreementPercent}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className={`h-full rounded-full ${
            agreementPercent >= 75 ? 'bg-green-500' :
            agreementPercent >= 50 ? 'bg-yellow-500' : 'bg-orange-500'
          }`}
        />
      </div>
      <div className="text-xs text-gray-500 mt-1">
        {consensus.top_votes} of {consensus.total_voters} models ranked <span className="text-gray-300">{topModelName}</span> first
      </div>
    </div>
  );
}

// Enhanced Aggregate Rankings display
function AggregateRankingsView({ rankings, votingMethod }: { rankings: AggregateRanking[]; votingMethod?: VotingMethod }) {
  if (!rankings?.length) return null;

  const getScoreLabel = (rank: AggregateRanking): string => {
    if (rank.borda_score !== undefined) {
      return `score: ${rank.borda_score}`;
    }
    if (rank.mrr_score !== undefined) {
      return `MRR: ${rank.mrr_score}`;
    }
    if (rank.weighted_score !== undefined) {
      return `weighted: ${rank.weighted_score}`;
    }
    return `avg: ${rank.average_rank.toFixed(2)}`;
  };

  return (
    <div className="bg-purple-900/20 border border-purple-700/50 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-purple-300">Aggregate Rankings</h4>
        <VotingMethodBadge method={votingMethod} />
      </div>
      <div className="space-y-2">
        {rankings.map((rank, idx) => {
          const modelName = rank.model.split('/').pop() || rank.model;
          const isTop = idx === 0;

          return (
            <div key={rank.model} className={`flex items-center gap-3 ${isTop ? 'bg-purple-800/30 -mx-2 px-2 py-1 rounded' : ''}`}>
              <span className={`text-lg font-bold w-6 ${isTop ? 'text-yellow-400' : 'text-purple-400'}`}>
                {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `${idx + 1}`}
              </span>
              <span className={`flex-1 text-sm ${isTop ? 'text-gray-100 font-medium' : 'text-gray-200'}`}>
                {modelName}
              </span>
              <span className="text-xs text-gray-400">
                {getScoreLabel(rank)} ({rank.rankings_count} votes)
              </span>
              {rank.confidence_boost !== undefined && rank.confidence_boost !== 0 && (
                <span className={`text-xs ${rank.confidence_boost > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {rank.confidence_boost > 0 ? '+' : ''}{rank.confidence_boost}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Stage 2: Peer Rankings
function Stage2View({ rankings, metadata }: { rankings: PeerEvaluation[]; metadata?: Metadata | null | undefined }) {
  if (!rankings?.length) return null;

  const deanonymize = (text: string) => {
    if (!metadata?.label_to_model) return text;
    let result = text;
    Object.entries(metadata.label_to_model).forEach(([label, model]) => {
      const modelName = model.split('/').pop() || model;
      result = result.replace(new RegExp(label, 'g'), `**${modelName}**`);
    });
    return result;
  };

  // Check if this is from a multi-round debate
  const hasDebateRounds = rankings.some(r => r.debate_round !== undefined && r.debate_round > 1);
  const hasRubricScores = rankings.some(r => r.rubric_scores && Object.keys(r.rubric_scores).length > 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">
          Stage 2: Peer Rankings
        </h3>
        {hasDebateRounds && (
          <span className="px-2 py-0.5 bg-blue-600/30 rounded text-xs text-blue-300">
            Multi-Round Debate
          </span>
        )}
        {hasRubricScores && (
          <span className="px-2 py-0.5 bg-yellow-600/30 rounded text-xs text-yellow-300">
            Rubric Evaluation
          </span>
        )}
      </div>

      <FeatureBadges metadata={metadata} />
      <ConsensusIndicator consensus={metadata?.consensus} />
      <AggregateRankingsView rankings={metadata?.aggregate_rankings || []} votingMethod={metadata?.voting_method} />

      {/* Individual Evaluations */}
      <div className="grid gap-3">
        {rankings.map((eval_, idx) => {
          const modelName = eval_.model.split('/').pop() || eval_.model;
          const roundLabel = eval_.debate_round ? ` (Round ${eval_.debate_round})` : '';

          return (
            <motion.div
              key={`${eval_.model}-${idx}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden"
            >
              <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
                <Bot size={14} className="text-gray-500" />
                <span className="text-sm font-medium text-gray-300">{modelName}'s Evaluation{roundLabel}</span>
              </div>
              <div className="p-4 prose prose-invert prose-sm max-w-none">
                <MarkdownRenderer content={deanonymize(eval_.ranking)} />
              </div>

              {/* Rubric Scores */}
              {eval_.rubric_scores && Object.keys(eval_.rubric_scores).length > 0 && (
                <div className="px-4 py-2 bg-yellow-900/10 border-t border-yellow-700/30">
                  <div className="text-xs font-medium text-yellow-400 mb-2">Rubric Scores:</div>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(eval_.rubric_scores).map(([responseLabel, scores]) => (
                      <div key={responseLabel} className="text-xs">
                        <span className="text-gray-400">{responseLabel}:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {Object.entries(scores).map(([criterion, score]) => (
                            <span key={criterion} className="px-1.5 py-0.5 bg-gray-700 rounded text-gray-300">
                              {criterion.slice(0, 3)}: {score}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {eval_.parsed_ranking?.length > 0 && (
                <div className="px-4 py-2 bg-gray-900/50 border-t border-gray-700 text-xs text-gray-400">
                  <span className="font-medium">Extracted ranking: </span>
                  {eval_.parsed_ranking.map((r, i) => {
                    const label = r;
                    const model = metadata?.label_to_model?.[label];
                    const name = model ? model.split('/').pop() : label;
                    return (
                      <span key={i}>
                        {i + 1}. {name}
                        {i < eval_.parsed_ranking.length - 1 ? ', ' : ''}
                      </span>
                    );
                  })}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

// Stage 3: Synthesis (with meta-evaluation support)
function Stage3View({ synthesis, metadata }: { synthesis: ModelResponse | SynthesisWithMeta; metadata?: Metadata | null | undefined }) {
  if (!synthesis) return null;

  // Check if it's a SynthesisWithMeta
  const isMeta = 'synthesis' in synthesis && 'meta_evaluation' in synthesis;
  const mainSynthesis = isMeta ? (synthesis as SynthesisWithMeta).synthesis : synthesis as ModelResponse;
  const metaEval = isMeta ? (synthesis as SynthesisWithMeta).meta_evaluation : undefined;

  const modelName = mainSynthesis.model.split('/').pop() || mainSynthesis.model;
  const chairmanInfo = metadata?.features?.chairman_model?.split('/').pop();
  const isRotating = metadata?.features?.rotating_chairman;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-green-400 uppercase tracking-wider">
          Stage 3: Chairman's Synthesis
        </h3>
        {isRotating && (
          <span className="px-2 py-0.5 bg-orange-600/30 rounded text-xs text-orange-300">
            Rotating Chairman
          </span>
        )}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-green-900/20 border border-green-700/50 rounded-lg overflow-hidden"
      >
        <div className="px-4 py-2 bg-green-900/30 border-b border-green-700/50 flex items-center gap-2">
          <Bot size={14} className="text-green-500" />
          <span className="text-sm font-medium text-green-300">Chairman: {modelName}</span>
          {isRotating && chairmanInfo && chairmanInfo !== modelName && (
            <span className="text-xs text-green-400/60">(selected by ranking)</span>
          )}
        </div>
        <div className="p-4 prose prose-invert prose-sm max-w-none">
          <MarkdownRenderer content={mainSynthesis.response} />
        </div>
      </motion.div>

      {/* Meta-evaluation */}
      {metaEval && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-blue-900/20 border border-blue-700/50 rounded-lg overflow-hidden"
        >
          <div className="px-4 py-2 bg-blue-900/30 border-b border-blue-700/50 flex items-center gap-2">
            <BarChart3 size={14} className="text-blue-500" />
            <span className="text-sm font-medium text-blue-300">
              Meta-Evaluation by {metaEval.model.split('/').pop()}
            </span>
          </div>
          <div className="p-4 prose prose-invert prose-sm max-w-none">
            <MarkdownRenderer content={metaEval.evaluation} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

// Loading indicator
function StageLoading({ stage }: { stage: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex items-center gap-3 p-4 bg-gray-800/50 border border-gray-700 rounded-lg"
    >
      <div className="flex space-x-1">
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
          className="w-2 h-2 bg-blue-500 rounded-full"
        />
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 0.6, repeat: Infinity, delay: 0.15 }}
          className="w-2 h-2 bg-blue-500 rounded-full"
        />
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 0.6, repeat: Infinity, delay: 0.3 }}
          className="w-2 h-2 bg-blue-500 rounded-full"
        />
      </div>
      <span className="text-sm text-gray-400">{stage}</span>
    </motion.div>
  );
}

// Message component
function MessageView({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        className="flex gap-3"
      >
        <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
          <User size={16} className="text-white" />
        </div>
        <div className="flex-1 space-y-2">
          {message.images && message.images.length > 0 && (
            <div className="flex gap-2 overflow-x-auto">
              {message.images.map((img, idx) => (
                <img key={idx} src={img} alt="User upload" className="h-48 w-auto rounded-lg border border-gray-700" />
              ))}
            </div>
          )}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 prose prose-invert prose-sm max-w-none">
            <MarkdownRenderer content={message.content} />
          </div>
        </div>
      </motion.div>
    );
  }

  const assistantMsg = message as AssistantMessage;
  const hasStage1Content = assistantMsg.stage1 || assistantMsg.streamingResponses;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-4 pl-11"
    >
      {/* Stage 1 */}
      {assistantMsg.loading?.stage1 && !hasStage1Content && <StageLoading stage="Council members are responding..." />}
      {hasStage1Content && (
        <Stage1View
          responses={assistantMsg.stage1 || []}
          streamingResponses={assistantMsg.streamingResponses}
        />
      )}

      {/* Stage 2 */}
      {assistantMsg.loading?.stage2 && <StageLoading stage="Council members are evaluating peers..." />}
      {assistantMsg.stage2 && <Stage2View rankings={assistantMsg.stage2} metadata={assistantMsg.metadata} />}

      {/* Stage 3 */}
      {assistantMsg.loading?.stage3 && <StageLoading stage="Chairman is synthesizing final answer..." />}
      {assistantMsg.stage3 && <Stage3View synthesis={assistantMsg.stage3} metadata={assistantMsg.metadata} />}
    </motion.div>
  );
}

export function DeliberationView() {
  const {
    activeConversation,
    activeConversationId,
    isLoading,
    addMessage,
    updateLastMessage,
    setLoading,
    setStage,
    setConversations,
  } = useCouncilStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  const handleSendMessage = async (content: string, images: string[] = []) => {
    if (!activeConversationId) return;

    // Get council settings from settings store
    const { councilSettings } = useSettingsStore.getState();

    // Build deliberation options from settings
    const options = {
      voting_method: councilSettings.votingMethod,
      use_rubric: councilSettings.useRubric,
      debate_rounds: councilSettings.debateRounds,
      enable_early_exit: councilSettings.enableEarlyExit,
      use_self_moa: councilSettings.useSelfMoA,
      rotating_chairman: councilSettings.rotatingChairman,
      meta_evaluate: councilSettings.metaEvaluate,
    };

    setLoading(true);
    addMessage({ role: 'user', content, images });
    addMessage({
      role: 'assistant',
      stage1: null,
      stage2: null,
      stage3: null,
      metadata: null,
      loading: { stage1: false, stage2: false, stage3: false },
      streamingResponses: {},
    });

    try {
      await api.sendMessageStream(activeConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setStage(1);
            updateLastMessage({
              loading: { stage1: true, stage2: false, stage3: false },
              streamingResponses: {},
            });
            break;

          case 'model_start':
            if (event.model) {
              updateLastMessage((prev: AssistantMessage) => ({
                streamingResponses: {
                  ...prev.streamingResponses,
                  [event.model!]: { content: '', isStreaming: true, isDone: false },
                },
              }));
            }
            break;

          case 'model_chunk':
            if (event.model && event.accumulated) {
              updateLastMessage((prev: AssistantMessage) => ({
                streamingResponses: {
                  ...prev.streamingResponses,
                  [event.model!]: {
                    content: event.accumulated!,
                    isStreaming: true,
                    isDone: false,
                  },
                },
              }));
            }
            break;

          case 'model_done':
            if (event.model) {
              updateLastMessage((prev: AssistantMessage) => ({
                streamingResponses: {
                  ...prev.streamingResponses,
                  [event.model!]: {
                    content: event.response?.response || prev.streamingResponses?.[event.model!]?.content || '',
                    isStreaming: false,
                    isDone: true,
                  },
                },
              }));
            }
            break;

          case 'model_error':
            if (event.model) {
              console.error(`Model ${event.model} error:`, event.error);
              updateLastMessage((prev: AssistantMessage) => ({
                streamingResponses: {
                  ...prev.streamingResponses,
                  [event.model!]: {
                    content: `Error: ${event.error}`,
                    isStreaming: false,
                    isDone: true,
                  },
                },
              }));
            }
            break;

          case 'stage1_complete':
            updateLastMessage({
              stage1: event.data as ModelResponse[],
              loading: { stage1: false, stage2: false, stage3: false },
              streamingResponses: undefined,
            });
            break;

          case 'stage2_start':
            setStage(2);
            updateLastMessage({ loading: { stage1: false, stage2: true, stage3: false } });
            break;

          case 'stage2_complete':
            updateLastMessage({
              stage2: event.data as PeerEvaluation[],
              metadata: event.metadata,
              loading: { stage1: false, stage2: false, stage3: false },
            });
            break;

          case 'stage3_start':
            setStage(3);
            updateLastMessage({ loading: { stage1: false, stage2: false, stage3: true } });
            break;

          case 'stage3_complete':
            updateLastMessage({
              stage3: event.data as ModelResponse | SynthesisWithMeta,
              loading: { stage1: false, stage2: false, stage3: false },
            });
            break;

          case 'title_complete':
            api.listConversations().then(setConversations);
            break;

          case 'complete':
            setStage(0);
            setLoading(false);
            api.listConversations().then(setConversations);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setLoading(false);
            setStage(0);
            break;
        }
      }, images, options);
    } catch (error) {
      console.error('Failed to send message:', error);
      setLoading(false);
      setStage(0);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <SidebarToggle />
      <SettingsToggle />
      <StatusPanelToggle />

      <div className="flex-1 overflow-y-auto p-6">
        {!activeConversation ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Bot size={48} className="mx-auto text-gray-600 mb-4" />
              <h2 className="text-xl font-semibold text-gray-400 mb-2">Welcome to LLM Council</h2>
              <p className="text-gray-500 max-w-md">
                Select a conversation or start a new one to begin deliberation with multiple AI models.
              </p>
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-6">
            <AnimatePresence mode="popLayout">
              {activeConversation.messages?.map((message, idx) => (
                <MessageView key={idx} message={message} />
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {activeConversation && (
        <InputComposer onSend={handleSendMessage} isLoading={isLoading} />
      )}
    </div>
  );
}
