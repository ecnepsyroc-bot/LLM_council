import { motion } from 'framer-motion';
import { MessageSquare, BarChart3, Sparkles, Check, Loader2 } from 'lucide-react';

interface ProgressTimelineProps {
  currentStage: 0 | 1 | 2 | 3;
  stage1Complete: boolean;
  stage2Complete: boolean;
  stage3Complete: boolean;
  compact?: boolean;
}

const stages = [
  { id: 1, name: 'Responses', shortName: 'S1', icon: MessageSquare, color: 'blue' },
  { id: 2, name: 'Rankings', shortName: 'S2', icon: BarChart3, color: 'purple' },
  { id: 3, name: 'Synthesis', shortName: 'S3', icon: Sparkles, color: 'green' },
];

export function ProgressTimeline({
  currentStage,
  stage1Complete,
  stage2Complete,
  stage3Complete,
  compact = false,
}: ProgressTimelineProps) {
  const getStageStatus = (stageId: number) => {
    if (stageId === 1) return stage1Complete ? 'complete' : currentStage === 1 ? 'active' : 'pending';
    if (stageId === 2) return stage2Complete ? 'complete' : currentStage === 2 ? 'active' : 'pending';
    if (stageId === 3) return stage3Complete ? 'complete' : currentStage === 3 ? 'active' : 'pending';
    return 'pending';
  };

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        {stages.map((stage, idx) => {
          const status = getStageStatus(stage.id);
          const isActive = status === 'active';
          const isComplete = status === 'complete';

          return (
            <div key={stage.id} className="flex items-center">
              <motion.div
                animate={isActive ? { scale: [1, 1.1, 1] } : {}}
                transition={{ duration: 1, repeat: isActive ? Infinity : 0 }}
                className={`
                  w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium
                  ${isComplete ? `bg-${stage.color}-600 text-white` : ''}
                  ${isActive ? `bg-${stage.color}-600/50 text-${stage.color}-300 ring-2 ring-${stage.color}-400` : ''}
                  ${status === 'pending' ? 'bg-gray-700 text-gray-500' : ''}
                `}
                title={stage.name}
              >
                {isComplete ? (
                  <Check size={12} />
                ) : isActive ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  stage.id
                )}
              </motion.div>
              {idx < stages.length - 1 && (
                <div
                  className={`w-3 h-0.5 ${
                    isComplete ? `bg-${stage.color}-500` : 'bg-gray-600'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-4">
      {stages.map((stage, idx) => {
        const status = getStageStatus(stage.id);
        const Icon = stage.icon;
        const isActive = status === 'active';
        const isComplete = status === 'complete';

        return (
          <div key={stage.id} className="flex items-center">
            <div className="flex flex-col items-center">
              <motion.div
                animate={isActive ? { scale: [1, 1.05, 1] } : {}}
                transition={{ duration: 1.5, repeat: isActive ? Infinity : 0 }}
                className={`
                  relative w-12 h-12 rounded-full flex items-center justify-center
                  transition-all duration-300
                  ${isComplete ? `bg-${stage.color}-600 text-white` : ''}
                  ${isActive ? `bg-${stage.color}-600/30 text-${stage.color}-300 ring-2 ring-${stage.color}-400 ring-offset-2 ring-offset-gray-900` : ''}
                  ${status === 'pending' ? 'bg-gray-800 text-gray-500 border-2 border-gray-700' : ''}
                `}
              >
                {isComplete ? (
                  <Check size={20} />
                ) : isActive ? (
                  <>
                    <Icon size={20} />
                    <motion.div
                      className={`absolute inset-0 rounded-full border-2 border-${stage.color}-400`}
                      animate={{ scale: [1, 1.2], opacity: [0.8, 0] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    />
                  </>
                ) : (
                  <Icon size={20} />
                )}
              </motion.div>
              <span
                className={`mt-2 text-xs font-medium ${
                  isComplete || isActive ? `text-${stage.color}-400` : 'text-gray-500'
                }`}
              >
                {stage.name}
              </span>
            </div>

            {idx < stages.length - 1 && (
              <div className="relative w-16 mx-2">
                <div className="h-0.5 bg-gray-700 w-full" />
                <motion.div
                  className={`absolute top-0 left-0 h-0.5 bg-${stage.color}-500`}
                  initial={{ width: 0 }}
                  animate={{ width: isComplete ? '100%' : '0%' }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Mini version for header
export function MiniProgressIndicator({
  currentStage,
  stage1Complete,
  stage2Complete,
  stage3Complete,
}: ProgressTimelineProps) {
  if (currentStage === 0 && !stage1Complete && !stage2Complete && !stage3Complete) {
    return null;
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-800 rounded-full">
      {stages.map((stage) => {
        const status =
          stage.id === 1 ? (stage1Complete ? 'complete' : currentStage === 1 ? 'active' : 'pending') :
          stage.id === 2 ? (stage2Complete ? 'complete' : currentStage === 2 ? 'active' : 'pending') :
          stage.id === 3 ? (stage3Complete ? 'complete' : currentStage === 3 ? 'active' : 'pending') :
          'pending';

        return (
          <motion.div
            key={stage.id}
            animate={status === 'active' ? { scale: [1, 1.2, 1] } : {}}
            transition={{ duration: 0.8, repeat: status === 'active' ? Infinity : 0 }}
            className={`
              w-2 h-2 rounded-full
              ${status === 'complete' ? `bg-${stage.color}-500` : ''}
              ${status === 'active' ? `bg-${stage.color}-400` : ''}
              ${status === 'pending' ? 'bg-gray-600' : ''}
            `}
            title={`${stage.name}: ${status}`}
          />
        );
      })}
    </div>
  );
}
