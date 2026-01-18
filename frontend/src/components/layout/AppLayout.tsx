import { motion, AnimatePresence } from 'framer-motion';
import { useCouncilStore } from '../../store/councilStore';
import { ConversationSidebar } from './ConversationSidebar';
import { CouncilStatusPanel } from './CouncilStatusPanel';
import { SettingsPanel } from '../settings/SettingsPanel';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { sidebarCollapsed, statusPanelCollapsed } = useCouncilStore();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gray-900 text-gray-100">
      {/* Settings Panel (slides in from right) */}
      <SettingsPanel />
      {/* Collapsible Sidebar */}
      <AnimatePresence mode="wait">
        <motion.div
          initial={false}
          animate={{
            width: sidebarCollapsed ? 0 : 280,
            opacity: sidebarCollapsed ? 0 : 1,
          }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="h-full overflow-hidden border-r border-gray-700 bg-gray-800"
        >
          <ConversationSidebar />
        </motion.div>
      </AnimatePresence>

      {/* Main Deliberation View */}
      <main className="flex-1 flex flex-col min-w-0 bg-gray-900">
        {children}
      </main>

      {/* Council Status Panel */}
      <AnimatePresence mode="wait">
        <motion.div
          initial={false}
          animate={{
            width: statusPanelCollapsed ? 0 : 260,
            opacity: statusPanelCollapsed ? 0 : 1,
          }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="h-full overflow-hidden border-l border-gray-700 bg-gray-800"
        >
          <CouncilStatusPanel />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
