import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Settings,
  X,
  Sun,
  Moon,
  Monitor,
  LayoutGrid,
  LayoutList,
  Layers,
  Users,
  Gauge,
  Accessibility,
  Palette,
  ChevronDown,
  ChevronRight,
  RotateCcw,
} from 'lucide-react';
import { useSettingsStore } from '../../store/settingsStore';
import type {
  ThemeMode,
  FontFamily,
  FontSize,
  Stage1Layout,
  ColorScheme,
  VotingMethod,
} from '../../types';

// Toggle Switch Component
function Toggle({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        ${checked ? 'bg-blue-600' : 'bg-gray-600'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <span
        className={`
          inline-block h-4 w-4 transform rounded-full bg-white transition-transform
          ${checked ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  );
}

// Select Component
function Select<T extends string>({
  value,
  options,
  onChange,
  disabled = false,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      disabled={disabled}
      className={`
        bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

// Number Input Component
function NumberInput({
  value,
  min,
  max,
  onChange,
  disabled = false,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      onChange={(e) => onChange(Math.min(max, Math.max(min, parseInt(e.target.value) || min)))}
      disabled={disabled}
      className={`
        bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-200 w-20
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    />
  );
}

// Section Header Component
function SectionHeader({
  icon: Icon,
  title,
  isOpen,
  onToggle,
}: {
  icon: React.ElementType;
  title: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center gap-3 py-2 text-left hover:bg-gray-800/50 rounded-lg px-2 -mx-2"
    >
      <Icon size={18} className="text-blue-400" />
      <span className="flex-1 font-medium text-gray-200">{title}</span>
      {isOpen ? (
        <ChevronDown size={16} className="text-gray-400" />
      ) : (
        <ChevronRight size={16} className="text-gray-400" />
      )}
    </button>
  );
}

// Setting Row Component
function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex-1 pr-4">
        <div className="text-sm text-gray-200">{label}</div>
        {description && <div className="text-xs text-gray-500 mt-0.5">{description}</div>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

export function SettingsPanel() {
  const {
    isOpen,
    closeSettings,
    uiPreferences,
    councilSettings,
    updateUIPreference,
    updateCouncilSetting,
    resetUIPreferences,
    resetCouncilSettings,
  } = useSettingsStore();

  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    appearance: true,
    layout: false,
    accessibility: false,
    council: true,
    advanced: false,
  });

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeSettings}
            className="fixed inset-0 bg-black/50 z-40"
          />

          {/* Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed right-0 top-0 h-full w-96 bg-gray-900 border-l border-gray-700 z-50 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <div className="flex items-center gap-2">
                <Settings size={20} className="text-blue-400" />
                <h2 className="text-lg font-semibold text-gray-100">Settings</h2>
              </div>
              <button
                onClick={closeSettings}
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
              >
                <X size={18} className="text-gray-400" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Appearance Section */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <SectionHeader
                  icon={Palette}
                  title="Appearance"
                  isOpen={openSections.appearance}
                  onToggle={() => toggleSection('appearance')}
                />
                <AnimatePresence>
                  {openSections.appearance && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pt-3 space-y-1">
                        <SettingRow label="Theme">
                          <div className="flex gap-1">
                            {[
                              { value: 'light' as ThemeMode, icon: Sun },
                              { value: 'dark' as ThemeMode, icon: Moon },
                              { value: 'system' as ThemeMode, icon: Monitor },
                            ].map(({ value, icon: Icon }) => (
                              <button
                                key={value}
                                onClick={() => updateUIPreference('theme', value)}
                                className={`p-2 rounded-lg transition-colors ${
                                  uiPreferences.theme === value
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                                }`}
                              >
                                <Icon size={16} />
                              </button>
                            ))}
                          </div>
                        </SettingRow>

                        <SettingRow label="Color Scheme">
                          <Select<ColorScheme>
                            value={uiPreferences.colorScheme}
                            onChange={(v) => updateUIPreference('colorScheme', v)}
                            options={[
                              { value: 'default', label: 'Default' },
                              { value: 'high-contrast', label: 'High Contrast' },
                              { value: 'colorblind-safe', label: 'Colorblind Safe' },
                            ]}
                          />
                        </SettingRow>

                        <SettingRow label="Font Family">
                          <Select<FontFamily>
                            value={uiPreferences.fontFamily}
                            onChange={(v) => updateUIPreference('fontFamily', v)}
                            options={[
                              { value: 'default', label: 'Default' },
                              { value: 'dyslexic', label: 'Dyslexia-Friendly' },
                              { value: 'mono', label: 'Monospace' },
                            ]}
                          />
                        </SettingRow>

                        <SettingRow label="Font Size">
                          <Select<FontSize>
                            value={uiPreferences.fontSize}
                            onChange={(v) => updateUIPreference('fontSize', v)}
                            options={[
                              { value: 'small', label: 'Small' },
                              { value: 'medium', label: 'Medium' },
                              { value: 'large', label: 'Large' },
                              { value: 'xlarge', label: 'Extra Large' },
                            ]}
                          />
                        </SettingRow>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Layout Section */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <SectionHeader
                  icon={LayoutGrid}
                  title="Layout"
                  isOpen={openSections.layout}
                  onToggle={() => toggleSection('layout')}
                />
                <AnimatePresence>
                  {openSections.layout && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pt-3 space-y-1">
                        <SettingRow
                          label="Stage 1 Layout"
                          description="How model responses are displayed"
                        >
                          <div className="flex gap-1">
                            {[
                              { value: 'stacked' as Stage1Layout, icon: LayoutList, label: 'Stacked' },
                              { value: 'grid' as Stage1Layout, icon: LayoutGrid, label: 'Grid' },
                              { value: 'tabs' as Stage1Layout, icon: Layers, label: 'Tabs' },
                            ].map(({ value, icon: Icon, label }) => (
                              <button
                                key={value}
                                onClick={() => updateUIPreference('stage1Layout', value)}
                                title={label}
                                className={`p-2 rounded-lg transition-colors ${
                                  uiPreferences.stage1Layout === value
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                                }`}
                              >
                                <Icon size={16} />
                              </button>
                            ))}
                          </div>
                        </SettingRow>

                        <SettingRow
                          label="Compact Mode"
                          description="Reduce spacing for more content"
                        >
                          <Toggle
                            checked={uiPreferences.compactMode}
                            onChange={(v) => updateUIPreference('compactMode', v)}
                          />
                        </SettingRow>

                        <SettingRow label="Show Timestamps">
                          <Toggle
                            checked={uiPreferences.showTimestamps}
                            onChange={(v) => updateUIPreference('showTimestamps', v)}
                          />
                        </SettingRow>

                        <SettingRow label="Auto-expand Responses">
                          <Toggle
                            checked={uiPreferences.autoExpandResponses}
                            onChange={(v) => updateUIPreference('autoExpandResponses', v)}
                          />
                        </SettingRow>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Accessibility Section */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <SectionHeader
                  icon={Accessibility}
                  title="Accessibility"
                  isOpen={openSections.accessibility}
                  onToggle={() => toggleSection('accessibility')}
                />
                <AnimatePresence>
                  {openSections.accessibility && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pt-3 space-y-1">
                        <SettingRow
                          label="Reduce Motion"
                          description="Minimize animations"
                        >
                          <Toggle
                            checked={uiPreferences.reduceMotion}
                            onChange={(v) => updateUIPreference('reduceMotion', v)}
                          />
                        </SettingRow>

                        <SettingRow
                          label="High Contrast"
                          description="Increase text contrast"
                        >
                          <Toggle
                            checked={uiPreferences.highContrast}
                            onChange={(v) => updateUIPreference('highContrast', v)}
                          />
                        </SettingRow>

                        <SettingRow label="Show Confidence Badges">
                          <Toggle
                            checked={uiPreferences.showConfidenceBadges}
                            onChange={(v) => updateUIPreference('showConfidenceBadges', v)}
                          />
                        </SettingRow>

                        <SettingRow label="Show Rubric Scores">
                          <Toggle
                            checked={uiPreferences.showRubricScores}
                            onChange={(v) => updateUIPreference('showRubricScores', v)}
                          />
                        </SettingRow>

                        <SettingRow label="Enable Code Preview">
                          <Toggle
                            checked={uiPreferences.enableCodePreview}
                            onChange={(v) => updateUIPreference('enableCodePreview', v)}
                          />
                        </SettingRow>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Council Settings Section */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <SectionHeader
                  icon={Users}
                  title="Council Settings"
                  isOpen={openSections.council}
                  onToggle={() => toggleSection('council')}
                />
                <AnimatePresence>
                  {openSections.council && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pt-3 space-y-1">
                        <SettingRow
                          label="Voting Method"
                          description="How rankings are aggregated"
                        >
                          <Select<VotingMethod>
                            value={councilSettings.votingMethod}
                            onChange={(v) => updateCouncilSetting('votingMethod', v)}
                            options={[
                              { value: 'simple', label: 'Simple Average' },
                              { value: 'borda', label: 'Borda Count' },
                              { value: 'mrr', label: 'Mean Reciprocal Rank' },
                              { value: 'confidence_weighted', label: 'Confidence Weighted' },
                            ]}
                          />
                        </SettingRow>

                        <SettingRow
                          label="Rubric Evaluation"
                          description="Score responses on multiple criteria"
                        >
                          <Toggle
                            checked={councilSettings.useRubric}
                            onChange={(v) => updateCouncilSetting('useRubric', v)}
                          />
                        </SettingRow>

                        <SettingRow
                          label="Debate Rounds"
                          description="Number of evaluation rounds"
                        >
                          <NumberInput
                            value={councilSettings.debateRounds}
                            min={1}
                            max={5}
                            onChange={(v) => updateCouncilSetting('debateRounds', v)}
                          />
                        </SettingRow>

                        <SettingRow
                          label="Early Exit"
                          description="Skip stages on high consensus"
                        >
                          <Toggle
                            checked={councilSettings.enableEarlyExit}
                            onChange={(v) => updateCouncilSetting('enableEarlyExit', v)}
                          />
                        </SettingRow>

                        <SettingRow
                          label="Rotating Chairman"
                          description="Top-ranked model becomes chairman"
                        >
                          <Toggle
                            checked={councilSettings.rotatingChairman}
                            onChange={(v) => updateCouncilSetting('rotatingChairman', v)}
                          />
                        </SettingRow>

                        <SettingRow
                          label="Meta-Evaluation"
                          description="Independent review of synthesis"
                        >
                          <Toggle
                            checked={councilSettings.metaEvaluate}
                            onChange={(v) => updateCouncilSetting('metaEvaluate', v)}
                          />
                        </SettingRow>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Advanced Section */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <SectionHeader
                  icon={Gauge}
                  title="Advanced"
                  isOpen={openSections.advanced}
                  onToggle={() => toggleSection('advanced')}
                />
                <AnimatePresence>
                  {openSections.advanced && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pt-3 space-y-1">
                        <SettingRow
                          label="Self-MoA Mode"
                          description="Sample from one model instead of many"
                        >
                          <Toggle
                            checked={councilSettings.useSelfMoA}
                            onChange={(v) => updateCouncilSetting('useSelfMoA', v)}
                          />
                        </SettingRow>

                        {councilSettings.useSelfMoA && (
                          <SettingRow
                            label="Self-MoA Samples"
                            description="Number of samples per query"
                          >
                            <NumberInput
                              value={councilSettings.selfMoaSamples}
                              min={2}
                              max={10}
                              onChange={(v) => updateCouncilSetting('selfMoaSamples', v)}
                            />
                          </SettingRow>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-gray-700 space-y-2">
              <button
                onClick={() => {
                  resetUIPreferences();
                  resetCouncilSettings();
                }}
                className="w-full flex items-center justify-center gap-2 py-2 px-4 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
              >
                <RotateCcw size={16} />
                Reset to Defaults
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
