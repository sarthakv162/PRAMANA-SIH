import { beforeEach, describe, expect, it } from 'vitest';
import { useAppStore } from './store';

describe('case file UI state', () => {
  beforeEach(() => useAppStore.setState({ caseFile: [] }));

  it('adds unique request IDs and removes an item', () => {
    const store = useAppStore.getState();
    store.addCaseItem({ request_id: 'req_1', summary: 'first' });
    useAppStore.getState().addCaseItem({ request_id: 'req_1', summary: 'duplicate' });
    expect(useAppStore.getState().caseFile).toHaveLength(1);
    useAppStore.getState().removeCaseItem('req_1');
    expect(useAppStore.getState().caseFile).toEqual([]);
  });

  it('reorders items within their valid range', () => {
    useAppStore.getState().addCaseItem({ request_id: 'req_1', summary: 'first' });
    useAppStore.getState().addCaseItem({ request_id: 'req_2', summary: 'second' });
    useAppStore.getState().moveCaseItem(1, -1);
    expect(useAppStore.getState().caseFile.map((item) => item.request_id)).toEqual(['req_2', 'req_1']);
    useAppStore.getState().moveCaseItem(0, -1);
    expect(useAppStore.getState().caseFile[0].request_id).toBe('req_2');
  });
});
