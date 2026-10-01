import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { EmptyState, PageHeading, Panel, Skeleton, StateMessage } from '../components/ui';

export function AdminPage() {
  const { t } = useTranslation();
  const [accessKey, setAccessKey] = useState('');
  const [submittedKey, setSubmittedKey] = useState('');
  const query = useQuery({
    queryKey: ['escalations', submittedKey],
    queryFn: () => api.escalations(submittedKey),
    enabled: Boolean(submittedKey),
  });

  return (
    <div className="page-stack">
      <PageHeading eyebrow="DEMO ADMIN · HIDDEN ROUTE" title={t('adminTitlePage')} description={t('adminDescription')} />
      <Panel className="admin-panel">
        <form className="admin-access-form" onSubmit={(event) => { event.preventDefault(); setSubmittedKey(accessKey); }}>
          <label htmlFor="admin-key">Admin access key</label>
          <input id="admin-key" type="password" autoComplete="current-password" value={accessKey} onChange={(event) => setAccessKey(event.target.value)} />
          <button className="button button-primary" type="submit" disabled={!accessKey}>{t('submit')}</button>
        </form>
        {query.isLoading && <Skeleton rows={4} />}
        {query.error && <StateMessage error={query.error} onRetry={() => void query.refetch()} />}
        {query.data?.length ? (
          <div className="table-scroll"><table><thead><tr><th>Ticket</th><th>Request</th><th>{t('status')}</th><th>{t('generated')}</th></tr></thead><tbody>
            {query.data.map((item) => <tr key={item.ticket_id}><td><code>{item.ticket_id}</code></td><td><code>{item.request_id}</code></td><td><span className="badge status-verified">{item.status}</span></td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}
          </tbody></table></div>
        ) : query.data && <EmptyState title={t('noTickets')} />}
      </Panel>
    </div>
  );
}
