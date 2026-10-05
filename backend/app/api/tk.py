"""POST /v1/tk-radar — ontology normalise + match + TKDL pack + watchlist (§6.10).

Seed data only (~20 plants, 10 classical formulations, 3 watchlist cases) — far short of the
~200/~100 target (§6.10); this is stated honestly rather than padded under time pressure.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit.rule_receipts import record_rule_engine_result
from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.fixtures import load_fixture
from app.retrieval.repo import live_corpus_version
from app.schemas.formulation import Formulation
from app.schemas.tk import (
    NormalizedIngredient,
    RadarAxis,
    RadarData,
    RegionalName,
    TkdlQuery,
    TkMatch,
    TkRadar,
    WatchlistHit,
)
from app.tk.matcher import match_formulations
from app.tk.ontology import normalize_ingredient
from app.tk.tkdl_query import build_tkdl_query
from app.tk.watchlist import matching_watchlist_hits

router = APIRouter(tags=["tk"])


@router.post("/tk-radar", response_model=TkRadar)
async def tk_radar(formulation: Formulation, session: Session = Depends(get_session)) -> TkRadar:
    settings = get_settings()
    if settings.mock_mode:
        return TkRadar.model_validate(load_fixture("tk_radar.json"))

    version = live_corpus_version(session)
    if version is None:
        raise ApiError(code="no_corpus", message="no live corpus_version", status_code=503)
    corpus_version_id, corpus_version_label = version

    names = [i.name for i in formulation.ingredients]

    normalized: list[NormalizedIngredient] = []
    for name in names:
        matches = normalize_ingredient(name)
        if matches:
            best = matches[0].entry
            normalized.append(
                NormalizedIngredient(
                    input=name,
                    canonical_latin=best.latin,
                    sanskrit=best.sanskrit,
                    regional=[RegionalName(lang=lang, name=n) for lang, n in best.regional.items()],
                    confidence=matches[0].confidence,
                )
            )

    match_results = match_formulations(names, formulation.intended_use)
    matches_out = [
        TkMatch(
            formulation_id=m.formulation.id,
            name=m.formulation.name,
            source_text=m.formulation.source_text,
            similarity=m.similarity,
            overlap=m.overlap,
            missing_in_input=m.missing_in_input,
            extra_in_input=m.extra_in_input,
            indication_match=m.indication_match,
            evidence_ids=[],
        )
        for m in match_results
        if m.similarity > 0
    ]

    radar = RadarData(axes=[RadarAxis(label=m.formulation.name, value=m.similarity) for m in match_results[:8]])

    tkdl = build_tkdl_query(names, formulation.intended_use)
    watchlist_hits = [
        WatchlistHit(
            case=c["case"],
            jurisdiction=c["jurisdiction"],
            summary=c["summary"],
            outcome=c["outcome"],
            source_url=c["source_url"],
        )
        for c in matching_watchlist_hits(names)
    ]

    tk_radar_result = TkRadar(
        normalized_ingredients=normalized,
        matches=matches_out,
        radar=radar,
        tkdl_query=TkdlQuery.model_validate(tkdl),
        watchlist_hits=watchlist_hits,
        receipt_id="",
    )
    receipt_id = record_rule_engine_result(
        session,
        corpus_version_id=corpus_version_id,
        corpus_version_label=corpus_version_label,
        endpoint="tk_radar",
        jurisdiction="IN",
        as_of=date.today(),
        request_payload=formulation.model_dump(mode="json"),
        evidence={},
        chunk_id_by_evidence_id={},
        result_payload=tk_radar_result.model_dump(mode="json"),
    )
    return tk_radar_result.model_copy(update={"receipt_id": receipt_id})
