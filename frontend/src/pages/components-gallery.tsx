import { useTranslation } from 'react-i18next';
import fixture from '../../../contracts/fixtures/answer_card_both_hi.json';
import { PageHeading, Panel, RiskBadge, StatusBadge, EvidenceQuote, EmptyState } from '../components/ui';
import type { EvidenceSpan } from '../api/types';

export function ComponentsPage() {
  const { t } = useTranslation(); const evidence = fixture.evidence.ev_7f3a9c as EvidenceSpan;
  return <div className="page-stack"><PageHeading eyebrow="DEVELOPMENT ONLY" title={t('components')} description="Reusable interface components rendered against a real contract fixture." />
    <div className="gallery-grid"><Panel><span className="eyebrow">STATUS BADGES</span><h2>Evidence status</h2><div className="row wrap"><StatusBadge status="verified" /><StatusBadge status="partial" /><StatusBadge status="not_in_indexed_documents" /></div></Panel><Panel><span className="eyebrow">RISK CHIPS</span><h2>Rule result</h2><div className="row"><RiskBadge risk="low" /><RiskBadge risk="medium" /><RiskBadge risk="high" /></div></Panel><Panel className="wide-gallery"><span className="eyebrow">VERBATIM QUOTE</span><h2>{t('evidence')}</h2><EvidenceQuote evidence={evidence} /></Panel><Panel><span className="eyebrow">EMPTY STATE</span><EmptyState title={t('noCaseItems')} /></Panel><Panel><span className="eyebrow">INTERACTION</span><h2>Buttons</h2><button className="button button-primary">Primary action →</button> <button className="button button-secondary">Secondary action</button></Panel></div>
  </div>;
}
