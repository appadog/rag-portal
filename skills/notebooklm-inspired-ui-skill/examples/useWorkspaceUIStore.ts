import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type PanelMode = 'hidden' | 'rail' | 'default' | 'expanded';

interface WorkspaceUIState {
  contextMode: PanelMode;
  outputMode: PanelMode;
  contextWidth: number;
  outputWidth: number;
  selectedContextIds: string[];
  activeContextId: string | null;
  activeOutputId: string | null;
  composerDraft: string;

  setContextMode: (mode: PanelMode) => void;
  setOutputMode: (mode: PanelMode) => void;
  setContextWidth: (width: number) => void;
  setOutputWidth: (width: number) => void;
  setSelectedContextIds: (ids: string[]) => void;
  setActiveContextId: (id: string | null) => void;
  setActiveOutputId: (id: string | null) => void;
  setComposerDraft: (value: string) => void;
}

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

export const useWorkspaceUIStore = create<WorkspaceUIState>()(
  persist(
    (set) => ({
      contextMode: 'default',
      outputMode: 'default',
      contextWidth: 300,
      outputWidth: 340,
      selectedContextIds: [],
      activeContextId: null,
      activeOutputId: null,
      composerDraft: '',

      setContextMode: (contextMode) => set({ contextMode }),
      setOutputMode: (outputMode) => set({ outputMode }),
      setContextWidth: (contextWidth) =>
        set({ contextWidth: clamp(contextWidth, 240, 420) }),
      setOutputWidth: (outputWidth) =>
        set({ outputWidth: clamp(outputWidth, 280, 480) }),
      setSelectedContextIds: (selectedContextIds) =>
        set({ selectedContextIds }),
      setActiveContextId: (activeContextId) =>
        set({ activeContextId }),
      setActiveOutputId: (activeOutputId) =>
        set({ activeOutputId }),
      setComposerDraft: (composerDraft) =>
        set({ composerDraft }),
    }),
    {
      name: 'workspace-ui',
      partialize: (state) => ({
        contextMode: state.contextMode,
        outputMode: state.outputMode,
        contextWidth: state.contextWidth,
        outputWidth: state.outputWidth,
        composerDraft: state.composerDraft,
      }),
    },
  ),
);
