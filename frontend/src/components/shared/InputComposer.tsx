import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Send, Loader2 } from 'lucide-react';

interface InputComposerProps {
  onSend: (content: string, images?: string[]) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function InputComposer({ onSend, isLoading, placeholder = 'Ask the council...' }: InputComposerProps) {
  const [input, setInput] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (const item of items) {
      if (item.type.indexOf('image') !== -1) {
        e.preventDefault();
        const blob = item.getAsFile();
        if (blob) {
          const reader = new FileReader();
          reader.onload = (event) => {
            if (event.target?.result) {
              setImages(prev => [...prev, event.target!.result as string]);
            }
          };
          reader.readAsDataURL(blob);
        }
      }
    }
  };

  const removeImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    if ((!input.trim() && images.length === 0) || isLoading) return;
    onSend(input.trim(), images);
    setInput('');
    setImages([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-gray-700 bg-gray-800/50 p-4">
      <div className="max-w-4xl mx-auto space-y-3">
        {/* Image Previews */}
        {images.length > 0 && (
          <div className="flex gap-2 overflow-x-auto py-2">
            {images.map((img, idx) => (
              <div key={idx} className="relative group flex-shrink-0">
                <img src={img} alt="Pasted" className="h-20 w-auto rounded-lg border border-gray-600" />
                <button
                  onClick={() => removeImage(idx)}
                  className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={placeholder}
              disabled={isLoading}
              rows={1}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-gray-100 placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '48px', maxHeight: '200px' }}
            />
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleSubmit}
            disabled={(!input.trim() && images.length === 0) || isLoading}
            className="flex-shrink-0 p-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl transition-colors disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Send size={20} />
            )}
          </motion.button>
        </div>
      </div>
      <div className="text-xs text-gray-500 text-center mt-2">
        Press Enter to send, Shift+Enter for new line. Paste images directly.
      </div>
    </div>
  );
}
