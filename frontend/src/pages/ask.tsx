import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { QUERY_STAGES, type EvidenceSpan, type QueryCard, type QueryRequest } from '../api/types';
import { EvidenceDrawer, EvidenceQuote, PageHeading, Panel, StateMessage, StatusBadge } from '../components/ui';
import { useAppStore } from '../state/store';
import { useQuerySSE } from '../hooks/useQuerySSE';

function useVoiceInput(onTranscript: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const { t } = useTranslation();
  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const instance = new MediaRecorder(stream);
      recorder.current = instance; chunks.current = [];
      instance.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      instance.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        try { const result = await api.asr(new Blob(chunks.current, { type: instance.mimeType || 'audio/webm' })); onTranscript(result.text); }
        catch { startBrowserSpeech(); }
      };
      instance.start(); setRecording(true);
    } catch { startBrowserSpeech(); }
  };
  const startBrowserSpeech = () => {
    const SpeechRecognition = (window as Window & { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike }).SpeechRecognition || (window as Window & { webkitSpeechRecognition?: new () => SpeechRecognitionLike }).webkitSpeechRecognition;
    if (!SpeechRecognition) { window.alert(t('voiceUnavailable')); return; }
    const speech = new SpeechRecognition(); speech.lang = useAppStore.getState().language === 'auto' ? 'hi-IN' : useAppStore.getState().language; speech.onresult = (event) => onTranscript(event.results[0][0].transcript); speech.start();
  };
  const stop = () => { recorder.current?.stop(); setRecording(false); };
  return { recording, start, stop };
}
interface SpeechRecognitionLike { lang: string; onresult: (event: { results: { 0: { transcript: string } }[] }) => void; start: () => void }

function ClaimCard({ card, claim, openEvidence }: { card: Extract<QueryCard, { type: 'answer' }>; claim: Extract<Extract<QueryCard, { type: 'answer' }>['sections'][number]['claims'][number], object>; openEvidence: (span: EvidenceSpan) => void }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const cited = claim.evidence_ids.map((id) => card.evidence[id]).filter(Boolean);
  return <article className="claim-card"><div className="claim-heading"><StatusBadge status={claim.status} /><div className="citation-chips">{cited.map((span, index) => <button key={span.id} className="citation-chip" onClick={() => openEvidence(span)} aria-label={`${t('openSource')}: ${span.citation_label}`}>[{index + 1}]</button>)}</div></div><p className="claim-text">{claim.text}</p>
    {cited.length > 0 && <button className="disclosure-button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? '−' : '+'} {t('statutoryText')}</button>}
    {expanded && <div className="claim-evidence">{cited.map((span) => <EvidenceQuote key={span.id} evidence={span} onOpen={() => openEvidence(span)} />)}</div>}
  </article>;
}

function AnswerCardView({ card, jurisdiction, onFollowup }: { card: Extract<QueryCard, { type: 'answer' }>; jurisdiction: string; onFollowup: (text: string) => void }) {
  const { t } = useTranslation();
  const health = useQuery({ queryKey: ['health'], queryFn: api.health });
  const addCase = useAppStore((state) => state.addCaseItem);
  const caseFile = useAppStore((state) => state.caseFile);
  const alreadyAdded = caseFile.some((item) => item.request_id === card.request_id);
  const [drawerEvidence, setDrawerEvidence] = useState<EvidenceSpan | null>(null);
  const [spoken, setSpoken] = useState(false);
  const spans = Object.values(card.evidence);
  const sections = jurisdiction === 'BOTH' ? card.sections : card.sections.filter((section) => section.jurisdiction === jurisdiction);
  const speak = async () => {
    if (spoken) { speechSynthesis.cancel(); setSpoken(false); return; }
    try { const claims = card.sections.flatMap((section) => section.claims.map((claim) => claim.text)).join('. '); const blob = await api.tts(claims, card.language); const url = URL.createObjectURL(blob); const audio = new Audio(url); audio.onended = () => { URL.revokeObjectURL(url); setSpoken(false); }; setSpoken(true); await audio.play(); }
    catch { const utterance = new SpeechSynthesisUtterance(card.sections.flatMap((section) => section.claims.map((claim) => claim.text)).join('. ')); utterance.lang = card.language === 'auto' ? 'en-IN' : card.language; utterance.onend = () => setSpoken(false); setSpoken(true); speechSynthesis.speak(utterance); }
  };
  const open = (evidence: EvidenceSpan) => setDrawerEvidence(evidence);
  return <>
    <Panel className="answer-panel"><div className="answer-topline"><div className="answer-tags"><span className="eyebrow">{health.data?.mock_mode === false ? t('liveAnswer') : t('reviewMock')}</span><span className="corpus-tag">{card.corpus_version}</span></div><div className="answer-actions"><span className={`confidence confidence-${card.confidence.level}`}>{t('confidence')} · {t(card.confidence.level)} {Math.round(card.confidence.score * 100)}%</span>{card.review_recommended && <span className="badge badge-review">⚑ {t('reviewRecommended')}</span>}</div></div>
      {card.dropped_claims > 0 && <div className="note warning-note">ⓘ {card.dropped_claims} {t('removedClaims')}</div>}
      <div className={jurisdiction === 'BOTH' ? 'jurisdiction-columns' : ''}>{sections.map((section) => {
        const used = new Set(section.claims.flatMap((claim) => claim.evidence_ids).map((id) => card.evidence[id]?.jurisdiction).filter(Boolean));
        return <section className="answer-section" key={section.jurisdiction}><header className="section-title"><div><span className="section-kicker">{section.jurisdiction}</span><h2>{section.heading}</h2></div><span className="small-muted">{used.size} {t('evidence').toLowerCase()} source{used.size === 1 ? '' : 's'}</span></header>
          {section.claims.length ? section.claims.map((claim) => <ClaimCard key={claim.id} card={card} claim={claim} openEvidence={open} />) : <div className="empty-inline">{t('empty')}</div>}
          {section.gaps.length > 0 && <div className="gaps"><b>{t('gaps')}</b>{section.gaps.map((gap, index) => <p key={index}>• {gap.text}</p>)}</div>}
        </section>;
      })}</div>
      {jurisdiction === 'BOTH' && <div className="separation-note">⊘ No cross-jurisdiction mixing · India: {spans.filter((span) => span.jurisdiction === 'IN').length} spans · International: {spans.filter((span) => span.jurisdiction === 'INTL').length} spans</div>}
      {card.glossary.length > 0 && <div className="glossary-row"><span>Language terms</span>{card.glossary.map((item) => <details key={item.term}><summary>{item.term}</summary><span>{item.gloss}</span></details>)}</div>}
      <div className="answer-bottom"><div className="followups"><b>{t('followups')}</b>{card.suggested_followups.map((followup) => <button className="followup-chip" key={followup} onClick={() => onFollowup(followup)}>{followup} →</button>)}</div><div className="answer-cta"><button className="button button-secondary" disabled={alreadyAdded} aria-live="polite" onClick={() => { const first = card.sections.flatMap((section) => section.claims)[0]; addCase({ request_id: card.request_id, summary: first?.text ?? 'PRAMANA result', receipt_id: card.receipt_id }); }}>{alreadyAdded ? t('addedToCase') : t('addToCase')}</button><button className="button button-secondary" onClick={() => void speak()}>{spoken ? t('stopListening') : `♫ ${t('listen')}`}</button><Link className="button button-secondary" to={`/receipt/${card.receipt_id}`}>{t('receipt')} ↗</Link></div></div>
    </Panel><EvidenceDrawer evidence={drawerEvidence} onClose={() => setDrawerEvidence(null)} onNavigate={(direction) => { const index = spans.findIndex((span) => span.id === drawerEvidence?.id); setDrawerEvidence(spans[(index + direction + spans.length) % spans.length] ?? null); }} />
  </>;
}

function EscalationForm({ refusal, onClose }: { refusal: Extract<QueryCard, { type: 'refusal' }>; onClose: () => void }) {
  const { t } = useTranslation(); const [contact, setContact] = useState(''); const [note, setNote] = useState(''); const [ticket, setTicket] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); setBusy(true); setError(''); try { const result = await api.escalate({ request_id: refusal.request_id, ...(contact ? { contact } : {}), ...(note ? { note } : {}) }); setTicket(result.ticket_id); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to create ticket.'); } finally { setBusy(false); } };
  return <div className="modal-backdrop"><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="escalate-heading"><header><h2 id="escalate-heading">{t('escalationsTitle')}</h2><button className="icon-button" onClick={onClose} aria-label={t('close')}>×</button></header>{ticket ? <div className="success-card"><div className="success-mark">✓</div><h3>{t('ticket')}</h3><code>{ticket}</code></div> : <form onSubmit={(event) => void submit(event)}><label>{t('contact')}<input value={contact} onChange={(event) => setContact(event.target.value)} autoComplete="email" /></label><label>{t('note')}<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={4} /></label>{error && <p className="field-error" role="alert">{error}</p>}<button className="button button-primary" disabled={busy}>{busy ? t('loading') : t('submit')}</button></form>}</section></div>;
}

function RefusalView({ card }: { card: Extract<QueryCard, { type: 'refusal' }> }) {
  const { t } = useTranslation(); const [escalate, setEscalate] = useState(false); const [drawer, setDrawer] = useState<EvidenceSpan | null>(null);
  return <><Panel className="refusal-panel"><div className="refusal-mark">!</div><span className="eyebrow">No supported answer</span><h2>{card.reason.replaceAll('_', ' ')}</h2><p>{card.message}</p>{card.nearest_sources.map((source) => <EvidenceQuote key={source.id} evidence={source} onOpen={() => setDrawer(source)} />)}<div className="answer-cta"><button className="button button-primary" onClick={() => setEscalate(true)}>{t('escalationsTitle')}</button><Link className="button button-secondary" to={`/receipt/${card.receipt_id}`}>{t('receipt')} ↗</Link></div></Panel><EvidenceDrawer evidence={drawer} onClose={() => setDrawer(null)} />{escalate && <EscalationForm refusal={card} onClose={() => setEscalate(false)} />}</>;
}

export function AskPage() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [turns, setTurns] = useState<{ id: number; query: string; card: QueryCard | null }[]>([]);
  const { jurisdiction, asOf, language, persona } = useAppStore();
  const { stages, error, isLoading, run, cancel } = useQuerySSE();
  const voice = useVoiceInput(setQuery);
  const newestTurnRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (turns.length) newestTurnRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [turns.length]);
  const send = async (text = query) => {
    if (!text.trim() || isLoading) return;
    const cleanText = text.trim();
    const id = Date.now();
    const body: QueryRequest = { query: cleanText, jurisdiction, as_of: asOf, language, persona, mode: voice.recording ? 'voice' : 'text', conversation_id: null, formulation: null };
    setTurns((previous) => [...previous, { id, query: cleanText, card: null }]);
    setQuery('');
    const response = await run(body);
    if (response) setTurns((previous) => previous.map((turn) => turn.id === id ? { ...turn, card: response } : turn));
  };
  const examples = ['Can traditional knowledge be patented in India?', 'What fees are listed in the indexed documents?'];
  const progress = useMemo(() => QUERY_STAGES.filter((stage) => stages[stage] === 'done').length, [stages]);
  const latestTurn = turns.at(-1);
  return <div className="page-stack ask-page">
    {turns.length > 0 && <PageHeading eyebrow="IP-SAKTI / SAHAYAK" title={t('askTitle')} description={t('askDescription')} />}
    {turns.length === 0 ? <section className="research-welcome" aria-label={t('researchTools')}>
      <div className="welcome-orbit orbit-one" aria-hidden="true" /><div className="welcome-orbit orbit-two" aria-hidden="true" />
      <div className="welcome-copy"><span className="welcome-kicker"><i /> {t('homeKicker')}</span><h1>{t('homeFirst')}<br /><em>{t('homeSecond')}</em></h1><p>{t('homeDescription')}</p>
        <div className="welcome-pills"><span><b>01</b> {t('heroPillOne')}</span><span><b>02</b> {t('heroPillTwo')}</span><span><b>03</b> {t('heroPillThree')}</span></div>
      </div>
      <div className="welcome-visual"><div className="visual-glow" aria-hidden="true" /><div className="visual-document" aria-hidden="true"><div className="doc-top"><span>IN</span><i>ACT · 1970</i></div><b>Patents Act</b><small>CHAPTER II — INVENTIONS NOT PATENTABLE</small><div className="doc-line wide" /><div className="doc-line" /><div className="doc-highlight">traditional knowledge <span>§ 3(p)</span></div><div className="doc-line short" /><div className="doc-foot"><span>● VERIFIED SOURCE</span><span>PAGE 12</span></div></div><Link className="floating-evidence" to="/corpus" aria-label={`${t('evidence')}: ${t('openSource')}`}><span className="evidence-spark" aria-hidden="true">✳</span><span><b>{t('evidence')}</b><small>Every claim, traceable</small></span><i aria-hidden="true">↗</i></Link>
      </div>
    </section> : <div className="conversation-thread" aria-live="polite">{turns.map((turn, index) => <section ref={index === turns.length - 1 ? newestTurnRef : undefined} className="conversation-turn" key={turn.id}>
      <div className="user-message"><span className="user-avatar">R</span><div><small>{t('yourQuestion')} <span>· {String(index + 1).padStart(2, '0')}</span></small><p>{turn.query}</p></div></div>
      {turn.card?.type === 'answer' && <div className="assistant-message"><div className="assistant-avatar">✳</div><div className="assistant-response"><div className="assistant-label"><span>PRAMANA <i>{t('verifiedResearch')}</i></span><button className="text-button" type="button" onClick={() => navigator.clipboard?.writeText(turn.card?.type === 'answer' ? turn.card.sections.flatMap((section) => section.claims.map((claim) => claim.text)).join('\n\n') : '')}>{t('copyAnswer')}</button></div><AnswerCardView card={turn.card} jurisdiction={turn.card.jurisdiction} onFollowup={(text) => void send(text)} /></div></div>}
      {turn.card?.type === 'refusal' && <div className="assistant-message"><div className="assistant-avatar">✳</div><div className="assistant-response"><RefusalView card={turn.card} /></div></div>}
      {isLoading && latestTurn?.id === turn.id && <Panel className="stepper-panel"><div className="stepper-head"><div><span className="eyebrow">RETRIEVAL PIPELINE</span><h2>{t('askPipeline')}</h2></div><div className="row"><span className="progress-label">{progress}/{QUERY_STAGES.length}</span><button className="text-button" onClick={cancel}>{t('cancel')}</button></div></div><ol className="stage-stepper">{QUERY_STAGES.map((stage, stageIndex) => <li key={stage} className={`stage-${stages[stage] ?? 'pending'}`}><span className="stage-dot">{stages[stage] === 'done' ? '✓' : stageIndex + 1}</span><span>{stage}</span></li>)}</ol></Panel>}
      {error && latestTurn?.id === turn.id && <StateMessage error={error} onRetry={() => void send(turn.query)} />}
    </section>)}</div>}
    {turns.length === 0 && <section className="tool-shelf" aria-label={t('researchTools')}><div className="tool-shelf-heading"><span>{t('exploreWorkspace')}</span><span>{t('traceableDecisions')}</span></div><div className="tool-shelf-grid">
      <Link to="/classify" className="tool-tile"><span className="tool-icon icon-classify">◈</span><span><b>{t('tileClassify')}</b><small>{t('tileClassifyDescription')}</small></span><i>↗</i></Link>
      <Link to="/patent-risk" className="tool-tile"><span className="tool-icon icon-risk">◇</span><span><b>{t('tileRisk')}</b><small>{t('tileRiskDescription')}</small></span><i>↗</i></Link>
      <Link to="/abs" className="tool-tile"><span className="tool-icon icon-abs">▤</span><span><b>{t('tileAbs')}</b><small>{t('tileAbsDescription')}</small></span><i>↗</i></Link>
    </div></section>}
    {error && turns.length === 0 && <StateMessage error={error} onRetry={() => void send()} />}
    <div className="composer-dock"><div className="query-context">{jurisdiction === 'BOTH' ? `${t('india')} + ${t('international')}` : jurisdiction === 'IN' ? t('india') : t('international')}<span>·</span>{new Date(`${asOf}T00:00:00`).toLocaleDateString()}<span>·</span>{t(persona)}</div>
      <form className="query-panel" onSubmit={(event) => { event.preventDefault(); void send(); }}><label htmlFor="query-input" className="sr-only">{t('queryPlaceholder')}</label><textarea id="query-input" placeholder={t('queryPlaceholder')} value={query} onChange={(event) => setQuery(event.target.value)} rows={2} disabled={isLoading} /><div className="composer-toolbar"><div className="composer-utilities"><button type="button" className={`icon-button mic-button ${voice.recording ? 'is-recording' : ''}`} aria-label={voice.recording ? t('stopListening') : t('listen')} onClick={() => voice.recording ? voice.stop() : void voice.start()}>{voice.recording ? '■' : <svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-4 0h8"/></svg>}</button>{voice.recording && <span className="small-muted">{t('recording')}</span>}<span className="composer-separator" /><span className="composer-scope">{jurisdiction === 'BOTH' ? t('twoJurisdictions') : t('indexedSources')}</span></div><button className="button button-primary composer-send" disabled={!query.trim() || isLoading} aria-label={isLoading ? t('loading') : t('send')}>{isLoading ? <span className="composer-spinner" /> : <span className="send-arrow">↑</span>}{isLoading ? t('loading') : t('send')}</button></div></form>
      {turns.length === 0 && <div className="example-row"><span>{t('examples')}</span>{examples.map((item) => <button key={item} className="example-chip" disabled={isLoading} onClick={() => void send(item)}>{item}<span>↗</span></button>)}</div>}
      <p className="composer-note">{t('composerDisclaimer')}</p>
    </div>
  </div>;
}
