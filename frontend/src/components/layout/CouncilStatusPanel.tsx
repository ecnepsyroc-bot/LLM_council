import { motion } from 'framer-motion';
import { ChevronRight, ChevronLeft, Bot, Loader2, CheckCircle, AlertCircle, Circle } from 'lucide-react';
import { useCouncilStore } from '../../store/councilStore';
import type { ModelStatus } from '../../types';

// Default council members - these should match your backend config
const COUNCIL_MEMBERS = [
  { id: 'openai/gpt-4o', name: 'GPT-4o' },
  { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet' },
  { id: 'google/gemini-2.0-flash-thinking-exp', name: 'Gemini 2.0 Flash' },
  { id: 'x-ai/grok-2-1212', name: 'Grok 2' },
  { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1' },
];

const CHAIRMAN = { id: 'google/gemini-2.0-pro-exp-02-05', name: 'Gemini 2.0 Pro (Chairman)' };

function getStatusIcon(status: ModelStatus) {
  switch (status) {
    case 'thinking':
    case 'responding':
    case 'evaluating':
      return <Loader2 size={14} className="animate-spin text-blue-400" />;
    case 'finished':
      return <CheckCircle size={14} className="text-green-400" />;
    case 'error':
      return <AlertCircle size={14} className="text-red-400" />;
    default:
      return <Circle size={14} className="text-gray-600" />;
  }
}

function getStatusText(status: ModelStatus, stage?: 1 | 2 | 3) {
  switch (status) {
    case 'thinking':
      return 'Thinking...';
    case 'responding':
      return stage === 1 ? 'Responding...' : 'Synthesizing...';
    case 'evaluating':
      return 'Evaluating peers...';
    case 'finished':
      return 'Complete';
    case 'error':
      return 'Error';
    default:
      return 'Idle';
  }
}

function getStatusColor(status: ModelStatus) {
  switch (status) {
    case 'thinking':
    case 'responding':
    case 'evaluating':
      return 'border-blue-500/50 bg-blue-500/10';
    case 'finished':
      return 'border-green-500/50 bg-green-500/10';
    case 'error':
      return 'border-red-500/50 bg-red-500/10';
    default:
      return 'border-gray-700 bg-gray-800/50';
  }
}

export function CouncilStatusPanel() {
  const { councilStatus, deliberation, statusPanelCollapsed, toggleStatusPanel } = useCouncilStore();

  const getStageLabel = () => {
    switch (deliberation.stage) {
      case 1:
        return 'Stage 1: Individual Responses';
      case 2:
        return 'Stage 2: Peer Evaluation';
      case 3:
        return 'Stage 3: Synthesis';
      default:
        return 'Ready';
    }
  };

  return (
    <div className="flex flex-col h-full w-[260px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <button
          onClick={toggleStatusPanel}
          className="p-1.5 rounded-md hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
          title="Collapse panel"
        >
          <ChevronRight size={18} />
        </button>
        <h2 className="text-sm font-semibold text-white">Council Status</h2>
      </div>

      {/* Current Stage */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Current Stage</div>
        <div className={`text-sm font-medium ${deliberation.stage > 0 ? 'text-blue-400' : 'text-gray-400'}`}>
          {getStageLabel()}
        </div>
      </div>

      {/* Council Members */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2 px-1">
          Council Members
        </div>
        <div className="space-y-2">
          {COUNCIL_MEMBERS.map((member) => {
            const status = councilStatus[member.id];
            const modelStatus = status?.status || 'idle';

            return (
              <motion.div
                key={member.id}
                initial={false}
                animate={{
                  scale: modelStatus === 'thinking' || modelStatus === 'responding' ? 1.02 : 1,
                }}
                className={`p-2.5 rounded-lg border transition-colors ${getStatusColor(modelStatus)}`}
              >
                <div className="flex items-center gap-2">
                  <Bot size={16} className="text-gray-500" />
                  <span className="text-sm text-gray-200 flex-1 truncate">{member.name}</span>
                  {getStatusIcon(modelStatus)}
                </div>
                <div className="text-xs text-gray-500 mt-1 ml-6">
                  {getStatusText(modelStatus, status?.currentStage)}
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Chairman */}
        <div className="mt-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2 px-1">
            Chairman
          </div>
          {(() => {
            const status = councilStatus[CHAIRMAN.id];
            const modelStatus = status?.status || 'idle';

            return (
              <motion.div
                initial={false}
                animate={{
                  scale: modelStatus === 'thinking' || modelStatus === 'responding' ? 1.02 : 1,
                }}
                className={`p-2.5 rounded-lg border transition-colors ${getStatusColor(modelStatus)}`}
              >
                <div className="flex items-center gap-2">
                  <Bot size={16} className="text-yellow-500" />
                  <span className="text-sm text-gray-200 flex-1 truncate">{CHAIRMAN.name}</span>
                  {getStatusIcon(modelStatus)}
                </div>
                <div className="text-xs text-gray-500 mt-1 ml-6">
                  {getStatusText(modelStatus, 3)}
                </div>
              </motion.div>
            );
          })()}
        </div>
      </div>

      {/* Footer Stats */}
      <div className="p-3 border-t border-gray-700">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-gray-800/50 rounded p-2">
            <div className="text-gray-500">Models</div>
            <div className="text-white font-medium">{COUNCIL_MEMBERS.length + 1}</div>
          </div>
          <div className="bg-gray-800/50 rounded p-2">
            <div className="text-gray-500">Stage</div>
            <div className="text-white font-medium">{deliberation.stage || '-'}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Collapsed panel toggle button
export function StatusPanelToggle() {
  const { statusPanelCollapsed, toggleStatusPanel } = useCouncilStore();

  if (!statusPanelCollapsed) return null;

  return (
    <motion.button
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={toggleStatusPanel}
      className="fixed right-2 top-4 z-50 p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
      title="Expand status panel"
    >
      <ChevronLeft size={18} />
    </motion.button>
  );
}
