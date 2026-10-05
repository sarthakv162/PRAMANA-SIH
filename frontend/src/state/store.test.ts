import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from './store';
import { api } from '../api/client';

vi.mock('../api/client', () => ({ workspaceConnected: () => true, api: { caseFile: vi.fn(), addCase: vi.fn(), removeCase: vi.fn(), orderCase: vi.fn() } }));
const one = { request_id: 'req_1', summary: 'first' };
const two = { request_id: 'req_2', summary: 'second' };

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
