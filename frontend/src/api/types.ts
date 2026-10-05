/* Reconciled against the real backend contract: contracts/openapi.yaml, generated into
 * src/api/types.gen.ts via `npm run types:generate` (see that file for the raw, 1:1
 * openapi-typescript output). This file re-derives the same ergonomic named interfaces the
 * app already used (AnswerCard, Claim, EvidenceSpan, ...) from backend/app/schemas/*.py, so
 * component call sites stay the same shape as before while every field name/type now matches
 * the frozen Pydantic contract instead of the plan-derived guesses this file used to hold.
 *
 * Fields the backend declares with a server-side default (e.g. `gaps: list[Gap] =
 * Field(default_factory=list)`) are kept required here: the real renderer always populates
 * them and every fixture includes them, so treating them as always-present keeps presentation
 * components unchanged, per IMPLEMENTATION_AUDIT.md's reconciliation note. Fields that are
 * genuinely optional/nullable in the schema (e.g. `DocumentSummary.issuer`,
 * `Formulation.resource_origin`) are typed as such below.
 */
export type Jurisdiction = 'IN' | 'INTL' | 'BOTH';
export type Language = 'auto' | 'en' | 'hi' | 'ta' | 'bn' | 'mr' | 'te' | 'gu' | 'kn' | 'ml' | 'pa' | 'or';
export type UiLanguage = 'en' | 'hi' | 'ta' | 'bn' | 'mr';
export type Persona = 'vaidya' | 'startup' | 'attorney' | 'licensing_officer' | 'researcher';
export type Risk = 'low' | 'medium' | 'high';
export type DocType = 'statute' | 'rule' | 'regulation' | 'treaty' | 'notification' | 'case' | 'guideline' | 'manual';
export type ApplicantType = 'indian_citizen' | 'indian_company' | 'foreign_entity' | 'nri';
export type Authority = 'NBA' | 'SBB' | 'BMC' | 'none';
export type AbsActivity = 'research' | 'commercial_utilisation' | 'ipr_application' | 'transfer_results' | 'export' | 'cultivation_trade';
export type ClassifyCategory = 'classical' | 'proprietary' | 'new_drug' | 'phytopharmaceutical' | 'aahar_nutraceutical' | 'cosmetic';

export interface Highlight { page: number; page_width: number; page_height: number; rects: number[][] }
export interface EvidenceSpan {
  id: string; doc_id: string; doc_title: string; doc_type: DocType; jurisdiction: 'IN' | 'INTL';
  citation_label: string; section_key: string; section_path: string[]; page: number; page_end: number;
  char_start: number; char_end: number; text: string; sha256: string; effective_from: string;
  effective_to: string | null; corpus_version: string; source_url: string; pdf_url: string;
  highlights: Highlight[];
}
export interface ClaimChecks { nli_entail: number; numbers_ok: boolean; dates_ok: boolean; negation_ok: boolean }
export interface Claim { id: string; text: string; status: 'verified' | 'partial' | 'not_in_indexed_documents'; evidence_ids: string[]; checks: ClaimChecks }
export interface Gap { text: string; status: 'not_in_indexed_documents' }
export interface AnswerCard {
  type: 'answer'; request_id: string; corpus_version: string; as_of: string; language: Language; detected_language: Language;
  jurisdiction: Jurisdiction; sections: { jurisdiction: 'IN' | 'INTL'; heading: string; claims: Claim[]; gaps: Gap[] }[];
  evidence: Record<string, EvidenceSpan>; glossary: { term: string; gloss: string; lang: Language }[];
  confidence: { level: 'high' | 'medium' | 'low'; score: number }; review_recommended: boolean; dropped_claims: number;
  translation: { back_translation_ok: boolean; note: string | null }; suggested_followups: string[]; receipt_id: string;
  disclaimer: string; timings_ms: { intake: number; retrieve: number; generate: number; verify: number; total: number };
}
export interface RefusalCard {
  type: 'refusal'; request_id: string; reason: 'generation_unavailable' | 'no_evidence' | 'out_of_scope' | 'low_confidence' | 'legal_advice_request' | 'jurisdiction_unclear' | 'deadline_exceeded';
  message: string; nearest_sources: EvidenceSpan[]; escalation: { available: boolean; prefill: { question: string; jurisdiction: Jurisdiction; as_of: string } | null };
  receipt_id: string; disclaimer: string;
}
export type QueryCard = AnswerCard | RefusalCard;
export interface QueryRequest { query: string; jurisdiction: Jurisdiction; as_of: string; language: Language; persona: Persona; mode: 'text' | 'voice'; conversation_id: string | null; formulation: Formulation | null }
export interface ApiError { error: { code: string; message: string; request_id: string } }
export interface CorpusVersion { label: string; status: 'live' | 'staged' | 'retired'; created_at: string }
export interface DocumentSummary { id: string; short_key: string; title: string; doc_type: DocType; jurisdiction: Jurisdiction; issuer: string | null; source_url: string; language: string; in_force_from: string; in_force_to: string | null }

export interface ResourceOrigin { state: string | null; wild_or_cultivated: 'wild' | 'cultivated' | null; codified_tk: boolean | null }
export interface Ingredient { name: string; part: string | null; role: 'active' | 'excipient' | null; amount: string | null }
export interface Formulation {
  name: string; intended_use: string; product_form: string; ingredients: Ingredient[];
  process_summary: string | null; classical_sources_cited: string[]; claims_novel_effect: boolean; novel_effect_evidence: string | null;
  has_clinical_data: boolean; is_derivative_of_known_substance: boolean; resource_origin: ResourceOrigin | null;
  applicant_type: ApplicantType | null; planned_actions: string[];
}
export interface DecisionNode { id: string; kind: 'question' | 'outcome'; label: string; value: string | null; evidence_ids: string[]; taken: true }
export interface DecisionEdge { from: string; to: string; label: string }
export interface DecisionPath { nodes: DecisionNode[]; edges: DecisionEdge[]; outcome_id: string }
export interface ClassifyQuestion {
  type: 'question'; question_id: string; text: string; why_asked: string;
  input: { kind: 'single' | 'multi' | 'boolean' | 'text'; options: { value: string; label: string }[]; fields?: { id: string; label: string; kind: 'single' | 'multi' | 'boolean' | 'text'; options: { value: string; label: string }[]; required: boolean }[] };
  evidence_ids: string[]; evidence: Record<string, EvidenceSpan>; progress: { answered: number; estimated_total: number };
}
export interface PostureItem { risk: Risk; note: string; evidence_ids: string[] }
/** Fixed-shape per backend/app/schemas/classify.py::IpPosture — not a free-form record. */
export interface IpPosture { patent: PostureItem; gi: PostureItem; trademark: PostureItem; design: PostureItem; copyright: PostureItem; trade_secret: PostureItem }
export interface ClassifyResult {
  type: 'result'; category: ClassifyCategory; category_label: string; requirements: { text: string; evidence_ids: string[] }[];
  ip_posture: IpPosture;
  abs_posture: { summary: string; evidence_ids: string[] }; decision_path: DecisionPath; evidence: Record<string, EvidenceSpan>; receipt_id: string;
}
export type ClassifyResponse = ClassifyQuestion | ClassifyResult;
export interface PatentRisk {
  type: 'patent_risk'; gauge: Risk; score: number;
  per_section: { section: string; risk: Risk; triggered_rules: string[]; reasons: string[]; evidence_ids: string[] }[];
  what_would_help: { text: string; evidence_ids: string[] }[]; decision_path: DecisionPath; evidence: Record<string, EvidenceSpan>;
  receipt_id: string; disclaimer: string;
}
export interface AbsRequest { applicant_type: ApplicantType; activity: AbsActivity[]; resources: { species: string; is_codified_tk: boolean; is_cultivated: boolean; state: string | null }[]; ipr_type?: string; as_of: string; language: Language }
export interface AbsResult { type: 'abs'; summary: string; assessment_status?: 'unassessed' | 'provisional'; checklist: { id: string; title: string; authority: Authority; form?: string; required: boolean | null; exempt: boolean | null; exempt_reason?: string; timing?: string; detail: string; evidence_ids: string[] }[]; decision_path: DecisionPath; evidence: Record<string, EvidenceSpan>; receipt_id: string }
export interface TkRadar {
  type: 'tk_radar'; normalized_ingredients: { input: string; canonical_latin: string; sanskrit: string | null; regional: { lang: string; name: string }[]; confidence: number }[];
  matches: { formulation_id: string; name: string; source_text: string; similarity: number; overlap: string[]; missing_in_input: string[]; extra_in_input: string[]; indication_match: boolean; evidence_ids: string[] }[];
  radar: { axes: { label: string; value: number }[] }; tkdl_query: { terms: string[]; ipc: string[]; text: string; note: string };
  watchlist_hits: { case: string; jurisdiction: 'IN' | 'INTL'; summary: string; outcome: string; source_url: string }[]; receipt_id: string;
}
/** model_ids is a fixed {llm, embed, nli} object per backend/app/schemas/receipts.py::ModelIds, not a free-form record. */
export interface ModelIds { llm: string; embed: string; nli: string }
export interface Receipt { id: string; request_id: string; corpus_version: string; query_hash: string; chunk_hashes: string[]; model_ids: ModelIds; prompt_version: string; prev_hash: string; entry_hash: string; created_at: string }
export interface VerifyResult { chain_valid: boolean; corpus_root: string; spans: { evidence_id: string; sha256: string; in_corpus: boolean; merkle_proof_valid: boolean }[] }
/** NOTE: the real EvalCondition (backend/app/schemas/eval.py) has no latency fields — the
 * provisional type's `latency_p50_ms`/`latency_p95_ms` do not exist on the frozen contract and
 * have been dropped. See IMPLEMENTATION_AUDIT.md's "Exact metric field names for latency"
 * question; the plan's §9 doesn't define a latency metric either, so this is a real
 * contract gap, not a naming difference — flagged for Ritwik/backend to decide whether to add
 * it to EvalCondition or drop the idea. */
export interface EvalResults { method?: string | null; run_id: string; corpus_version: string; n_questions: number; conditions: { name: string; citation_precision: number; citation_recall: number; faithfulness: number | null; abstention_accuracy: number; jurisdiction_leaks: number }[]; risk_coverage: { threshold: number; coverage: number; risk: number }[]; generated_at: string }
export interface EscalationRequest { request_id: string; contact?: string; note?: string }
export interface EscalationResponse { ticket_id: string; status: string }
/** GET /v1/escalations is typed `list[dict[str, Any]]` server-side (additionalProperties:
 * true in the generated schema — see types.gen.ts), so openapi-typescript can't give it a
 * named shape. This interface instead mirrors the real row shape built by
 * `app/escalations.py::list_escalations` (and the mock-mode list in `app/api/escalations.py`),
 * which is `{ticket_id, request_id, contact, note, status, created_at}`. */
export interface EscalationItem { ticket_id: string; request_id: string; contact: string | null; note: string | null; status: string; created_at: string }
export interface AsrResponse { text: string; language: Language }
/** models is a fixed {llm, embed, nli} object per backend/app/schemas/health.py::ModelsStatus. */
export interface ModelsStatus { llm: string; embed: string; nli: string }
export interface HealthResponse { status: string; mock_mode: boolean; corpus_version: string; models: ModelsStatus; public_demo_mode?: boolean; inference_runtime?: 'ollama' | 'transformers'; storage_mode?: 'persistent' | 'ephemeral'; query_transport?: 'sse' | 'gradio' }
export type DossierFormat = 'pdf' | 'docx' | 'md';

export const QUERY_STAGES = ['intake', 'frame', 'cache', 'route', 'retrieve', 'resolve', 'generate', 'verify', 'render', 'audit'] as const;
export type QueryStage = typeof QUERY_STAGES[number];
export interface StageEvent { name: QueryStage; status: 'running' | 'done' | 'skipped' | 'failed'; ms?: number }

export interface ConversationSummary { id: string; title: string; workspace_id: string; created_at: string; updated_at: string; expires_at: string }
export interface SavedMessage { id: string; role: 'user' | 'assistant'; content: string; request_id: string | null; created_at: string; result: QueryCard | null }
export interface ConversationDetail extends ConversationSummary { messages: SavedMessage[] }
export interface SavedResult { request_id: string; conversation_id: string | null; result: QueryCard; receipt_id: string; created_at: string; expires_at: string }
export interface CaseRef { request_id: string; summary: string; receipt_id?: string | null }
export interface CoverageResponse { corpus_version: string | null; topics: { id: string; title: string; jurisdiction: string; status: string; missing_sources: string[]; indexed_sources: string[]; official_urls: string[]; note?: string }[]; source_check: { checked_at: string; next_check_at: string; checks: { source_id: string; status: string }[] } | null }
