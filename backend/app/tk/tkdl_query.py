"""§6.10 TKDL query builder: TKDL itself isn't publicly queryable, so this produces a search
term/IPC pack for an authorised examiner or the applicant's counsel — never a live query.
"""

from __future__ import annotations

from app.tk.ontology import normalize_ingredient

NOTE = (
    "TKDL access is restricted; this pack is for use by an authorised examiner "
    "or via the applicant's counsel."
)

# A61K 36/... is the IPC family for medicinal-plant preparations; a few common sub-classes
# by broad indication, illustrative rather than exhaustive.
_IPC_BY_INDICATION = {
    "skin": "A61K 36/00",
    "wound": "A61K 36/00",
    "digestion": "A61K 36/9068",
    "respiratory": "A61K 36/00",
    "cough": "A61K 36/9066",
    "immunity": "A61K 36/00",
    "joint": "A61K 36/00",
    "fever": "A61K 36/00",
}


def build_tkdl_query(ingredient_names: list[str], indication: str | None = None) -> dict[str, object]:
    terms: list[str] = []
    for name in ingredient_names:
        matches = normalize_ingredient(name)
        if matches:
            entry = matches[0].entry
            terms.extend([entry.latin, entry.sanskrit, *entry.regional.values()])
        else:
            terms.append(name)

    ipc = sorted({v for k, v in _IPC_BY_INDICATION.items() if indication and k in indication.lower()})
    if not ipc:
        ipc = ["A61K 36/00"]

    text = (
        f"Search terms: {', '.join(dict.fromkeys(terms))}\n"
        f"Candidate IPC/CPC classes: {', '.join(ipc)}\n"
        f"Indication: {indication or 'not specified'}\n"
        f"{NOTE}"
    )
    return {"terms": list(dict.fromkeys(terms)), "ipc": ipc, "text": text, "note": NOTE}
