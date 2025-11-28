import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, MessageSquare, ChevronLeft, ChevronRight } from 'lucide-react';
import { useCouncilStore } from '../../store/councilStore';
import { api } from '../../api';

export function ConversationSidebar() {
  const {
    conversations,
    activeConversationId,
    sidebarCollapsed,
    setConversations,
    setActiveConversation,
    updateConversation,
    toggleSidebar,
  } = useCouncilStore();

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, title: 'New Conversation', created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setActiveConversation(newConv.id);

      // Load the full conversation
      const fullConv = await api.getConversation(newConv.id);
      updateConversation(fullConv);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = async (id: string) => {
    setActiveConversation(id);
    try {
      const conv = await api.getConversation(id);
      updateConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  return (
    <div className="flex flex-col h-full w-[280px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <h1 className="text-lg font-semibold text-white">LLM Council</h1>
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-md hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
          title="Collapse sidebar"
        >
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* New Conversation Button */}
      <div className="p-3">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
        >
          <Plus size={18} />
          New Conversation
        </motion.button>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2">
        {conversations.length === 0 ? (
          <div className="text-center text-gray-500 py-8 text-sm">
            No conversations yet
          </div>
        ) : (
          <div className="space-y-1 py-2">
            {conversations.map((conv) => (
              <motion.button
                key={conv.id}
                whileHover={{ x: 2 }}
                onClick={() => handleSelectConversation(conv.id)}
                className={`w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors ${
                  conv.id === activeConversationId
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-300 hover:bg-gray-700/50'
                }`}
              >
                <MessageSquare size={18} className="mt-0.5 flex-shrink-0 text-gray-500" />
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm font-medium">
                    {conv.title || 'New Conversation'}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {conv.message_count} messages
                  </div>
                </div>
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-700">
        <div className="text-xs text-gray-500 text-center">
          Multi-model deliberation system
        </div>
      </div>
    </div>
  );
}

// Collapsed sidebar toggle button
export function SidebarToggle() {
  const { sidebarCollapsed, toggleSidebar } = useCouncilStore();

  if (!sidebarCollapsed) return null;

  return (
    <motion.button
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={toggleSidebar}
      className="fixed left-2 top-4 z-50 p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
      title="Expand sidebar"
    >
      <ChevronRight size={18} />
    </motion.button>
  );
}
