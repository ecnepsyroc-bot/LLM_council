import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, MessageSquare, ChevronLeft, ChevronRight, Trash2, Pin, Eye, EyeOff, Edit2, Check, X } from 'lucide-react';
import { useCouncilStore } from '../../store/councilStore';
import { api } from '../../api';
import { Conversation } from '../../types';

function EditableTitle({ title, onSave }: { title: string; onSave: (newTitle: string) => void }) {
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
    }
  }, [isEditing]);

  const handleSave = () => {
    if (value.trim() && value.trim() !== title) {
      onSave(value.trim());
    } else {
      setValue(title);
    }
    setIsEditing(false);
  };

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    setValue(title);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setValue(title);
      setIsEditing(false);
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center gap-1 min-w-0 flex-1" onClick={e => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          className="bg-gray-900 text-white text-sm px-1 py-0.5 rounded border border-blue-500 outline-none w-full min-w-0"
        />
        <button onMouseDown={handleSave} className="text-green-400 hover:text-green-300 p-0.5 flex-shrink-0"><Check size={14} /></button>
        <button onMouseDown={handleCancel} className="text-gray-400 hover:text-gray-300 p-0.5 flex-shrink-0"><X size={14} /></button>
      </div>
    );
  }

  return (
    <div className="group/title flex items-center gap-2 min-w-0 flex-1">
      <span className="truncate">{title || 'New Conversation'}</span>
      <button
        onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
        className="opacity-0 group-hover/title:opacity-100 text-gray-500 hover:text-white transition-opacity p-0.5 flex-shrink-0"
        title="Rename"
      >
        <Edit2 size={12} />
      </button>
    </div>
  );
}

function ConversationItem({ conversation }: { conversation: Conversation }) {
  const {
    activeConversationId,
    setActiveConversation,
    updateConversation,
    deleteConversation,
    togglePin,
    toggleHide,
  } = useCouncilStore();

  const handleSelectConversation = async (id: string) => {
    setActiveConversation(id);
    try {
      const conv = await api.getConversation(id);
      updateConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleDeleteConversation = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this conversation?')) {
      await deleteConversation(id);
    }
  };

  const handleTogglePin = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await togglePin(id);
  };

  const handleToggleHide = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await toggleHide(id);
  };

  const handleUpdateTitle = async (newTitle: string) => {
    try {
      const updated = await api.updateConversation(conversation.id, { title: newTitle });
      updateConversation(updated);
    } catch (error) {
      console.error('Failed to update title:', error);
    }
  };

  return (
    <div className="relative group">
      <motion.button
        whileHover={{ x: 2 }}
        onClick={() => handleSelectConversation(conversation.id)}
        className={`w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors pr-16 ${
          conversation.id === activeConversationId
            ? 'bg-gray-700 text-white'
            : 'text-gray-300 hover:bg-gray-700/50'
        } ${conversation.is_hidden ? 'opacity-50' : ''}`}
      >
        <MessageSquare size={18} className="mt-0.5 flex-shrink-0 text-gray-500" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium flex items-center">
            <EditableTitle title={conversation.title} onSave={handleUpdateTitle} />
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            {conversation.message_count} messages
          </div>
        </div>
      </motion.button>
      
      <div className="absolute right-2 top-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => handleTogglePin(e, conversation.id)}
          className={`p-1 rounded-md hover:bg-gray-600/50 transition-colors ${conversation.is_pinned ? 'text-blue-400' : 'text-gray-400 hover:text-white'}`}
          title={conversation.is_pinned ? "Unpin conversation" : "Pin conversation"}
        >
          <Pin size={14} className={conversation.is_pinned ? "fill-current" : ""} />
        </button>
        <button
          onClick={(e) => handleToggleHide(e, conversation.id)}
          className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-600/50 transition-colors"
          title={conversation.is_hidden ? "Unhide conversation" : "Hide conversation"}
        >
          {conversation.is_hidden ? <Eye size={14} /> : <EyeOff size={14} />}
        </button>
        <button
          onClick={(e) => handleDeleteConversation(e, conversation.id)}
          className="p-1 rounded-md text-gray-400 hover:text-red-400 hover:bg-gray-600/50 transition-colors"
          title="Delete conversation"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

export function ConversationSidebar() {
  const {
    conversations,
    setConversations,
    setActiveConversation,
    toggleSidebar,
    showHidden,
    toggleShowHidden,
  } = useCouncilStore();

  useEffect(() => {
    const loadConversations = async () => {
      try {
        const data = await api.listConversations();
        setConversations(data);
      } catch (error) {
        console.error('Failed to list conversations:', error);
      }
    };
    loadConversations();
  }, [setConversations]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([newConv, ...conversations]);
      setActiveConversation(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
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
          <div className="space-y-4 py-2">
            {/* Pinned Conversations */}
            {conversations.some(c => c.is_pinned && (!c.is_hidden || showHidden)) && (
              <div className="space-y-1">
                <div className="px-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Pinned
                </div>
                {conversations
                  .filter(c => c.is_pinned && (!c.is_hidden || showHidden))
                  .map(conv => (
                    <ConversationItem key={conv.id} conversation={conv} />
                  ))}
              </div>
            )}

            {/* Recent Conversations */}
            <div className="space-y-1">
              <div className="px-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Recent
              </div>
              {conversations
                .filter(c => !c.is_pinned && (!c.is_hidden || showHidden))
                .map(conv => (
                  <ConversationItem key={conv.id} conversation={conv} />
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-700 space-y-2">
        <button
          onClick={toggleShowHidden}
          className="w-full flex items-center justify-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1"
        >
          {showHidden ? <EyeOff size={12} /> : <Eye size={12} />}
          {showHidden ? 'Hide hidden conversations' : 'Show hidden conversations'}
        </button>
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
