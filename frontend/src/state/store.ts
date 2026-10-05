import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Formulation, Jurisdiction, Language, Persona, UiLanguage } from '../api/types';
import { api, workspaceConnected } from '../api/client';
import { localISODate } from '../lib/date';

interface CaseItem { request_id: string; summary: string; receipt_id?: string | null }
export type ThemeMode = 'light' | 'dark';
interface AppState {
  jurisdiction: Jurisdiction; asOf: string; dateMode: 'today' | 'historical'; language: Language; uiLanguage: UiLanguage; persona: Persona; theme: ThemeMode;
  caseError: string; refreshCase: () => Promise<void>;
  caseFile: CaseItem[]; formulationDraft: Formulation;
  setJurisdiction: (value: Jurisdiction) => void; setAsOf: (value: string) => void;
  refreshAsOf: (reset?: boolean) => void;
  setLanguage: (value: Language) => void; setUiLanguage: (value: UiLanguage) => void;
  setPersona: (value: Persona) => void; setTheme: (value: ThemeMode) => void; addCaseItem: (value: CaseItem) => void;
  removeCaseItem: (id: string) => void; moveCaseItem: (index: number, direction: -1 | 1) => void;
  setFormulationDraft: (value: Formulation) => void;
}

export const emptyFormulation: Formulation = {
  name: '', intended_use: '', product_form: '', ingredients: [{ name: '', part: '', role: 'active', amount: '' }],
  process_summary: '', classical_sources_cited: [], claims_novel_effect: false, novel_effect_evidence: '',
  has_clinical_data: false, is_derivative_of_known_substance: false,
  resource_origin: { state: '', wild_or_cultivated: null, codified_tk: false }, applicant_type: null, planned_actions: [],
};
const today = localISODate;

function savedPreferences(state: Partial<AppState>) {
  return {
    jurisdiction: state.jurisdiction ?? 'BOTH', language: state.language ?? 'auto',
    uiLanguage: state.uiLanguage ?? 'en', persona: state.persona ?? 'vaidya', theme: state.theme ?? 'light',
  };
}

export const useAppStore = create<AppState>()(persist((set, get) => ({
  jurisdiction: 'BOTH', asOf: today(), dateMode: 'today', language: 'auto', uiLanguage: 'en', persona: 'vaidya', theme: 'light',
  caseFile: [], formulationDraft: emptyFormulation,
  setJurisdiction: (jurisdiction) => set({ jurisdiction }),
  setAsOf: (value) => {
    const asOf = value || today();
    set({ asOf, dateMode: asOf === today() ? 'today' : 'historical' });
  },
  refreshAsOf: (reset = false) => {
    if (reset || get().dateMode === 'today') set({ asOf: today(), dateMode: 'today' });
  },
  setLanguage: (language) => set({ language }), setUiLanguage: (uiLanguage) => set({ uiLanguage }),
  setPersona: (persona) => set({ persona }), setTheme: (theme) => set({ theme }),
  caseError: '',
  refreshCase: async () => {
    if (!workspaceConnected()) { set({ caseFile: [], caseError: '' }); return; }
    try { set({ caseFile: await api.caseFile(), caseError: '' }); }
    catch (cause) { set({ caseError: cause instanceof Error ? cause.message : 'Unable to load the case file.' }); }
  },
  addCaseItem: (item) => {
    void api.addCase(item.request_id).then((caseFile) => set({ caseFile, caseError: '' }))
      .catch((cause: unknown) => set({ caseError: cause instanceof Error ? cause.message : 'Unable to save the case item.' }));
  },
  removeCaseItem: (id) => {
    void api.removeCase(id).then((caseFile) => set({ caseFile, caseError: '' }))
      .catch((cause: unknown) => set({ caseError: cause instanceof Error ? cause.message : 'Unable to remove the case item.' }));
  },
  moveCaseItem: (index, direction) => {
    const current = useAppStore.getState().caseFile;
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const ordered = [...current]; [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    void api.orderCase(ordered.map((item) => item.request_id)).then((caseFile) => set({ caseFile, caseError: '' }))
      .catch((cause: unknown) => set({ caseError: cause instanceof Error ? cause.message : 'Unable to reorder the case file.' }));
  },
  setFormulationDraft: (formulationDraft) => set({ formulationDraft }),
}), {
  name: 'pramana-ui-state', version: 2,
  migrate: (persisted) => savedPreferences((persisted ?? {}) as Partial<AppState>),
  // Existing browsers may still have an old saved asOf. Ignore it on every opening.
  merge: (persisted, current) => ({ ...current, ...savedPreferences((persisted ?? {}) as Partial<AppState>), asOf: today(), dateMode: 'today' }),
  partialize: (state: AppState) => savedPreferences(state),
}));
