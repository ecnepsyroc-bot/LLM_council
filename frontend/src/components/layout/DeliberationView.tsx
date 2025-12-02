import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Bot } from 'lucide-react';
import { MarkdownRenderer } from '../shared/MarkdownRenderer';
import { useCouncilStore } from '../../store/councilStore';
import { InputComposer } from '../shared/InputComposer';
import { SidebarToggle } from './ConversationSidebar';
import { StatusPanelToggle } from './CouncilStatusPanel';
import { api } from '../../api';
import type { Message, AssistantMessage, ModelResponse, PeerEvaluation } from '../../types';

// Stage 1: Individual Responses
function Stage1View({ responses }: { responses: ModelResponse[] }) {
  if (!responses?.length) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">
        Stage 1: Individual Responses
      </h3>
      <div className="grid gap-3">
        {responses.map((resp, idx) => {
          const modelName = resp.model.split('/').pop() || resp.model;
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden"
            >
              <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
                <Bot size={14} className="text-gray-500" />
                <span className="text-sm font-medium text-gray-300">{modelName}</span>
              </div>
              <div className="p-4 prose prose-invert prose-sm max-w-none">
                <MarkdownRenderer content={resp.response} />
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

// Stage 2: Peer Rankings
function Stage2View({ rankings, metadata }: { rankings: PeerEvaluation[]; metadata?: { label_to_model: Record<string, string>; aggregate_rankings: Array<{ model: string; average_rank: number; rankings_count: number }> } | null }) {
  if (!rankings?.length) return null;

  // De-anonymize function
  const deanonymize = (text: string) => {
    if (!metadata?.label_to_model) return text;
    let result = text;
    Object.entries(metadata.label_to_model).forEach(([label, model]) => {
      const modelName = model.split('/').pop() || model;
      result = result.replace(new RegExp(label, 'g'), `**${modelName}**`);
    });
    return result;
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">
        Stage 2: Peer Rankings
      </h3>

      {/* Aggregate Rankings */}
      {metadata?.aggregate_rankings && (
        <div className="bg-purple-900/20 border border-purple-700/50 rounded-lg p-4 mb-4">
          <h4 className="text-sm font-medium text-purple-300 mb-3">Aggregate Rankings</h4>
          <div className="space-y-2">
            {metadata.aggregate_rankings.map((rank, idx) => {
              const modelName = rank.model.split('/').pop() || rank.model;
              return (
                <div key={rank.model} className="flex items-center gap-3">
                  <span className="text-lg font-bold text-purple-400 w-6">{idx + 1}</span>
                  <span className="flex-1 text-sm text-gray-200">{modelName}</span>
                  <span className="text-xs text-gray-400">
                    avg: {rank.average_rank.toFixed(2)} ({rank.rankings_count} votes)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Individual Evaluations */}
      <div className="grid gap-3">
        {rankings.map((eval_, idx) => {
          const modelName = eval_.model.split('/').pop() || eval_.model;
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden"
            >
              <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
                <Bot size={14} className="text-gray-500" />
                <span className="text-sm font-medium text-gray-300">{modelName}'s Evaluation</span>
              </div>
              <div className="p-4 prose prose-invert prose-sm max-w-none">
                <MarkdownRenderer content={deanonymize(eval_.ranking)} />
              </div>
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

// Stage 3: Synthesis
function Stage3View({ synthesis }: { synthesis: ModelResponse }) {
  if (!synthesis) return null;

  const modelName = synthesis.model.split('/').pop() || synthesis.model;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-green-400 uppercase tracking-wider">
        Stage 3: Chairman's Synthesis
      </h3>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-green-900/20 border border-green-700/50 rounded-lg overflow-hidden"
      >
        <div className="px-4 py-2 bg-green-900/30 border-b border-green-700/50 flex items-center gap-2">
          <Bot size={14} className="text-green-500" />
          <span className="text-sm font-medium text-green-300">Chairman: {modelName}</span>
        </div>
        <div className="p-4 prose prose-invert prose-sm max-w-none">
          <MarkdownRenderer content={synthesis.response} />
        </div>
      </motion.div>
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
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
          <User size={16} className="text-white" />
        </div>
        <div className="flex-1 bg-gray-800 border border-gray-700 rounded-lg p-4 prose prose-invert prose-sm max-w-none">
          <MarkdownRenderer content={message.content} />
        </div>
      </motion.div>
    );
  }

  const assistantMsg = message as AssistantMessage;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-4 pl-11"
    >
      {/* Stage 1 */}
      {assistantMsg.loading?.stage1 && <StageLoading stage="Council members are responding..." />}
      {assistantMsg.stage1 && <Stage1View responses={assistantMsg.stage1} />}

      {/* Stage 2 */}
      {assistantMsg.loading?.stage2 && <StageLoading stage="Council members are evaluating peers..." />}
      {assistantMsg.stage2 && <Stage2View rankings={assistantMsg.stage2} metadata={assistantMsg.metadata} />}

      {/* Stage 3 */}
      {assistantMsg.loading?.stage3 && <StageLoading stage="Chairman is synthesizing final answer..." />}
      {assistantMsg.stage3 && <Stage3View synthesis={assistantMsg.stage3} />}
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
    conversations,
  } = useCouncilStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  const handleSendMessage = async (content: string) => {
    if (!activeConversationId) return;

    setLoading(true);

    // Add user message
    addMessage({ role: 'user', content });

    // Add placeholder assistant message
    addMessage({
      role: 'assistant',
      stage1: null,
      stage2: null,
      stage3: null,
      metadata: null,
      loading: { stage1: false, stage2: false, stage3: false },
    });

    try {
      await api.sendMessageStream(activeConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setStage(1);
            updateLastMessage({ loading: { stage1: true, stage2: false, stage3: false } });
            break;

          case 'stage1_complete':
            updateLastMessage({
              stage1: event.data as ModelResponse[],
              loading: { stage1: false, stage2: false, stage3: false },
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
              stage3: event.data as ModelResponse,
              loading: { stage1: false, stage2: false, stage3: false },
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
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
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      setLoading(false);
      setStage(0);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toggle buttons for collapsed panels */}
      <SidebarToggle />
      <StatusPanelToggle />

      {/* Messages area */}
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

      {/* Input */}
      {activeConversation && (
        <InputComposer onSend={handleSendMessage} isLoading={isLoading} />
      )}
    </div>
  );
}
