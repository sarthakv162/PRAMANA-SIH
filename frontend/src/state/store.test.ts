import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from './store';
import { api } from '../api/client';

vi.mock('../api/client', () => ({ workspaceConnected: () => true, api: { caseFile: vi.fn(), addCase: vi.fn(), removeCase: vi.fn(), orderCase: vi.fn() } }));
const one = { request_id: 'req_1', summary: 'first' };
const two = { request_id: 'req_2', summary: 'second' };

describe('current date on reopening', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2030, 0, 31, 23, 59));
    localStorage.clear();
    useAppStore.getState().refreshAsOf(true);
  });
  afterEach(() => { vi.useRealTimers(); localStorage.clear(); });

  it.each([0, 1, 2])('ignores old saved dates for storage version %s and preserves preferences', async (version) => {
    localStorage.setItem('pramana-ui-state', JSON.stringify({
      version, state: { asOf: '2020-01-01', jurisdiction: 'IN', theme: 'dark', language: 'hi' },
    }));
    await useAppStore.persist.rehydrate();
    expect(useAppStore.getState()).toMatchObject({ asOf: '2030-01-31', dateMode: 'today', jurisdiction: 'IN', theme: 'dark', language: 'hi' });
  });

  it('uses the new day after reopening and never saves a historical date', async () => {
    useAppStore.getState().setAsOf('2020-01-01');
    expect(useAppStore.getState().asOf).toBe('2020-01-01');
    const saved = JSON.parse(localStorage.getItem('pramana-ui-state')!);
    expect(saved.state).not.toHaveProperty('asOf');
    vi.setSystemTime(new Date(2030, 1, 1, 0, 1));
    await useAppStore.persist.rehydrate();
    expect(useAppStore.getState().asOf).toBe('2030-02-01');
  });

  it('follows midnight in today mode while preserving intentional historical research in this session', () => {
    vi.setSystemTime(new Date(2030, 1, 1, 0, 1));
    useAppStore.getState().refreshAsOf();
    expect(useAppStore.getState().asOf).toBe('2030-02-01');
    useAppStore.getState().setAsOf('2020-01-01');
    useAppStore.getState().refreshAsOf();
    expect(useAppStore.getState().asOf).toBe('2020-01-01');
    useAppStore.getState().refreshAsOf(true);
    expect(useAppStore.getState().asOf).toBe('2030-02-01');
  });

  it('returns to today if the date input is cleared', () => {
    useAppStore.getState().setAsOf('');
    expect(useAppStore.getState()).toMatchObject({ asOf: '2030-01-31', dateMode: 'today' });
  });
});

describe('server-backed case file', () => {
  beforeEach(() => { vi.clearAllMocks(); useAppStore.setState({ caseFile: [], caseError: '' }); });
  it('reloads the shared saved references from the API', async () => {
    vi.mocked(api.caseFile).mockResolvedValue([one]);
    await useAppStore.getState().refreshCase();
    expect(useAppStore.getState().caseFile).toEqual([one]);
  });
  it('saves and removes references using server results', async () => {
    vi.mocked(api.addCase).mockResolvedValue([one]);
    useAppStore.getState().addCaseItem(one);
    await vi.waitFor(() => expect(useAppStore.getState().caseFile).toEqual([one]));
    expect(api.addCase).toHaveBeenCalledWith('req_1');
    vi.mocked(api.removeCase).mockResolvedValue([]);
    useAppStore.getState().removeCaseItem('req_1');
    await vi.waitFor(() => expect(useAppStore.getState().caseFile).toEqual([]));
  });
  it('preserves current state when the server rejects a save', async () => {
    vi.mocked(api.addCase).mockRejectedValue(new Error('Result expired'));
    useAppStore.getState().addCaseItem(one);
    await vi.waitFor(() => expect(useAppStore.getState().caseError).toBe('Result expired'));
    expect(useAppStore.getState().caseFile).toEqual([]);
  });
  it('sends the full new order and accepts the server order', async () => {
    useAppStore.setState({ caseFile: [one, two] });
    vi.mocked(api.orderCase).mockResolvedValue([two, one]);
    useAppStore.getState().moveCaseItem(1, -1);
    await vi.waitFor(() => expect(useAppStore.getState().caseFile).toEqual([two, one]));
    expect(api.orderCase).toHaveBeenCalledWith(['req_2', 'req_1']);
  });
});
