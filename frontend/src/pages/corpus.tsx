import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PageHeading, Panel, Skeleton, StateMessage, EmptyState } from '../components/ui';

export function CorpusPage() {
  const { t } = useTranslation(); const [jurisdiction, setJurisdiction] = useState(''); const [docType, setDocType] = useState(''); const [search, setSearch] = useState('');
  const docs = useQuery({ queryKey: ['documents', jurisdiction, docType], queryFn: () => api.documents(jurisdiction || undefined, docType || undefined) });
  const coverage = useQuery({ queryKey: ['coverage'], queryFn: api.coverage });
  const versions = useQuery({ queryKey: ['versions'], queryFn: api.versions });
  const rows = docs.data?.filter((item) => `${item.title} ${item.issuer}`.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <div className="page-stack"><PageHeading eyebrow={t('sourceLibrary').toUpperCase()} title={t('corpusTitle')} description={t('corpusDescription')} />
    <Panel><h2>Official-source coverage</h2><p className="small-muted">Indexed status records document availability; it does not certify that every provision or amendment is current.</p>
      {coverage.error && <StateMessage error={coverage.error} />}
      <div className="table-scroll"><table><thead><tr><th>Topic</th><th>Jurisdiction</th><th>Coverage</th><th>Missing sources / note</th></tr></thead><tbody>{coverage.data?.topics.map((topic) => <tr key={topic.id}><td>{topic.title}</td><td>{topic.jurisdiction}</td><td>{topic.status.replaceAll('_', ' ')}</td><td>{topic.missing_sources.join(', ') || topic.note || 'Listed sources indexed'}</td></tr>)}</tbody></table></div>
      <p className="small-muted">{coverage.data?.source_check ? `Source check: ${new Date(coverage.data.source_check.checked_at).toLocaleString()}. Next check: ${new Date(coverage.data.source_check.next_check_at).toLocaleString()}.` : 'Weekly source checks are configured; no completed check is recorded yet.'}</p>
      {coverage.data?.source_check?.checks.some((check) => check.status === 'check_failed') && <p className="field-error">Source checks failed for: {coverage.data.source_check.checks.filter((check) => check.status === 'check_failed').map((check) => check.source_id).join(', ')}. Their current source content has not been verified.</p>}
    </Panel>
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
