import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PageHeading, Panel, Skeleton, StateMessage, EmptyState } from '../components/ui';

export function CorpusPage() {
  const { t } = useTranslation(); const [jurisdiction, setJurisdiction] = useState(''); const [docType, setDocType] = useState(''); const [search, setSearch] = useState('');
  const docs = useQuery({ queryKey: ['documents', jurisdiction, docType], queryFn: () => api.documents(jurisdiction || undefined, docType || undefined) });
  const versions = useQuery({ queryKey: ['versions'], queryFn: api.versions });
  const rows = docs.data?.filter((item) => `${item.title} ${item.issuer}`.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <div className="page-stack"><PageHeading eyebrow={t('sourceLibrary').toUpperCase()} title={t('corpusTitle')} description={t('corpusDescription')} />
    <Panel className="filter-panel" aria-label={t('filter')}>
      <label className="search-field">{t('search')}<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('searchTitleIssuer')} /></label>
      <label>{t('jurisdiction')}<select value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}><option value="">{t('allSources')}</option><option value="IN">{t('india')}</option><option value="INTL">{t('international')}</option></select></label>
      <label>{t('docType')}<select value={docType} onChange={(event) => setDocType(event.target.value)}><option value="">{t('allDocTypes')}</option>{['statute', 'rule', 'regulation', 'treaty', 'notification', 'case', 'guideline', 'manual'].map((item) => <option key={item}>{item}</option>)}</select></label>
    </Panel>
    <Panel className="corpus-panel">
      <div className="section-title"><div><span className="eyebrow">{t('documents').toUpperCase()}</span><h2>{docs.isLoading ? '—' : rows.length} {t('indexedSources')}</h2></div><span className="small-muted">{versions.data?.filter((item) => item.status === 'live').length ?? 0} {t('liveVersions')}</span></div>
      {docs.isLoading && <Skeleton rows={4} />}
      {docs.error && <StateMessage error={docs.error} onRetry={() => void docs.refetch()} />}
      {docs.data && (rows.length ? <div className="table-scroll"><table><thead><tr><th scope="col">{t('documents')}</th><th scope="col">{t('jurisdiction')}</th><th scope="col">{t('docType')}</th><th scope="col">{t('effectiveDates')}</th><th scope="col">{t('source')}</th></tr></thead><tbody>{rows.map((doc) => <tr key={doc.id}><td><b>{doc.title}</b><small className="table-subline">{doc.issuer} · {doc.short_key}</small></td><td><span className="juris-pill">{doc.jurisdiction}</span></td><td>{doc.doc_type}</td><td>{doc.in_force_from}{doc.in_force_to ? ` — ${doc.in_force_to}` : ` — ${t('present')}`}</td><td><a href={doc.source_url} target="_blank" rel="noreferrer">{t('openSource')} ↗</a></td></tr>)}</tbody></table></div> : <EmptyState title={t('empty')} />)}
    </Panel>
    <Panel><span className="eyebrow">{t('versions').toUpperCase()}</span><h2>{t('versions')}</h2>{versions.isLoading ? <Skeleton rows={2} /> : versions.error ? <StateMessage error={versions.error} onRetry={() => void versions.refetch()} /> : <div className="version-list">{versions.data?.map((item) => <div className="version-line" key={item.label}><span><b>{item.label}</b><small>{new Date(item.created_at).toLocaleString()}</small></span><span className={`badge version-${item.status}`}>{item.status}</span></div>)}</div>}</Panel>
  </div>;
}
