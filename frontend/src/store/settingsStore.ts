import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  UIPreferences,
  CouncilSettings,
  ThemeMode,
  FontFamily,
  FontSize,
  Stage1Layout,
  ColorScheme,
  VotingMethod,
} from '../types';
import {
  DEFAULT_UI_PREFERENCES,
  DEFAULT_COUNCIL_SETTINGS,
} from '../types';

interface SettingsState {
  // Panel state
  isOpen: boolean;
  openSettings: () => void;
  closeSettings: () => void;
  toggleSettings: () => void;

  // UI Preferences
  uiPreferences: UIPreferences;
  updateUIPreference: <K extends keyof UIPreferences>(key: K, value: UIPreferences[K]) => void;
  resetUIPreferences: () => void;

  // Council Settings
  councilSettings: CouncilSettings;
  updateCouncilSetting: <K extends keyof CouncilSettings>(key: K, value: CouncilSettings[K]) => void;
  resetCouncilSettings: () => void;

  // Apply theme to document
  applyTheme: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      // Panel state
      isOpen: false,
      openSettings: () => set({ isOpen: true }),
      closeSettings: () => set({ isOpen: false }),
      toggleSettings: () => set((state) => ({ isOpen: !state.isOpen })),

      // UI Preferences
      uiPreferences: DEFAULT_UI_PREFERENCES,
      updateUIPreference: (key, value) => {
        set((state) => ({
          uiPreferences: { ...state.uiPreferences, [key]: value },
        }));
        // Apply theme changes immediately
        if (key === 'theme' || key === 'fontFamily' || key === 'fontSize' || key === 'colorScheme' || key === 'highContrast' || key === 'reduceMotion') {
          setTimeout(() => get().applyTheme(), 0);
        }
      },
      resetUIPreferences: () => {
        set({ uiPreferences: DEFAULT_UI_PREFERENCES });
        setTimeout(() => get().applyTheme(), 0);
      },

      // Council Settings
      councilSettings: DEFAULT_COUNCIL_SETTINGS,
      updateCouncilSetting: (key, value) => {
        set((state) => ({
          councilSettings: { ...state.councilSettings, [key]: value },
        }));
      },
      resetCouncilSettings: () => set({ councilSettings: DEFAULT_COUNCIL_SETTINGS }),

      // Apply theme to document
      applyTheme: () => {
        const { uiPreferences } = get();
        const root = document.documentElement;
        const body = document.body;

        // Theme
        let effectiveTheme = uiPreferences.theme;
        if (effectiveTheme === 'system') {
          effectiveTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        root.classList.remove('theme-light', 'theme-dark');
        root.classList.add(`theme-${effectiveTheme}`);
        body.classList.remove('light-mode', 'dark-mode');
        body.classList.add(effectiveTheme === 'dark' ? 'dark-mode' : 'light-mode');

        // Font family
        root.classList.remove('font-default', 'font-dyslexic', 'font-mono');
        root.classList.add(`font-${uiPreferences.fontFamily}`);

        // Font size
        root.classList.remove('text-small', 'text-medium', 'text-large', 'text-xlarge');
        root.classList.add(`text-${uiPreferences.fontSize}`);

        // Color scheme
        root.classList.remove('color-default', 'color-high-contrast', 'color-colorblind-safe');
        root.classList.add(`color-${uiPreferences.colorScheme}`);

        // High contrast - enable if toggle is on OR if colorScheme is high-contrast
        const isHighContrast = uiPreferences.highContrast || uiPreferences.colorScheme === 'high-contrast';
        root.classList.toggle('high-contrast', isHighContrast);

        // Reduce motion
        root.classList.toggle('reduce-motion', uiPreferences.reduceMotion);
      },
    }),
    {
      name: 'llm-council-settings',
      partialize: (state) => ({
        uiPreferences: state.uiPreferences,
        councilSettings: state.councilSettings,
      }),
      onRehydrateStorage: () => (state) => {
        // Apply theme after rehydration
        if (state) {
          setTimeout(() => state.applyTheme(), 0);
        }
      },
    }
  )
);
