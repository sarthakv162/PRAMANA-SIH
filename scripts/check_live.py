"""Exercise real saved history, synthesis, citations and receipts through the HTTP API."""
import json
import os
import time
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
base = os.environ.get('PRAMANA_TEST_URL', 'http://127.0.0.1:8080/v1')
headers = {'X-Demo-Key': env['DEMO_KEY']}


def query(client, question, conversation_id):
    response = client.post('/query', json={'query': question, 'jurisdiction': 'IN', 'language': 'en', 'conversation_id': conversation_id})
    response.raise_for_status()
    result = None
    for event in response.text.split('\n\n'):
        if event.startswith('event: result\n'):
            result = json.loads(event.split('data: ', 1)[1])
        if event.startswith('event: error\n'):
            raise RuntimeError(event)
    assert result, response.text[-1500:]
    return result


with httpx.Client(base_url=base, headers=headers, timeout=240) as client:
    ready_by = time.monotonic() + 90
    while True:
        try:
            if client.get('/health', timeout=5).status_code == 200: break
        except httpx.RequestError: pass
        if time.monotonic() > ready_by: raise RuntimeError('Production backend did not become ready.')
        time.sleep(1)
    created = client.post('/conversations', json={'title': 'Live acceptance check'})
    created.raise_for_status()
    conversation = created.json()
    cid = conversation['id']
    result = query(client, 'Summarize section 3(p) of the Patents Act and its introductory section.', cid)
    print('Actual local query:', result['type'], result.get('reason'), result.get('receipt_id'))
    assert result['type'] == 'answer', result
    claims = [c for section in result['sections'] for c in section['claims']]
    assert any(c['status'] == 'verified' for c in claims), claims
    for claim in claims:
        assert all(id in result['evidence'] for id in claim['evidence_ids'])
    receipt = client.post('/receipts/' + result['receipt_id'] + '/verify').json()
    assert receipt['chain_valid'] and all(s['in_corpus'] and s['merkle_proof_valid'] for s in receipt['spans'])
    saved = client.get('/requests/' + result['request_id']).json()
    assert saved['result'] == result
    refs = client.post('/case-file/' + result['request_id']).json()
    assert any(r['request_id'] == result['request_id'] for r in refs)
    dossier = client.post('/dossier', json={'items': [result['request_id']], 'format': 'md', 'language': 'en'})
    assert dossier.status_code == 200 and result['evidence'][claims[0]['evidence_ids'][0]]['text'] in dossier.text
    resumed = client.get('/conversations/' + cid).json()
    assert len(resumed['messages']) == 2
    broad = query(client, 'Can traditional knowledge be patented in India?', None)
    print('Broad phrasing:', broad['type'], [c['status'] for s in broad.get('sections', []) for c in s['claims']])
    followup = query(client, 'What does that exclusion cover?', cid)
    print('Follow-up:', followup['type'], followup.get('reason'), followup.get('receipt_id'))
    out = query(client, 'What is the weather today?', cid)
    assert out['type'] == 'refusal' and out['reason'] == 'out_of_scope'
    missing = query(client, 'What does the unindexed Patent Cooperation Treaty article 99 say?', None)
    print('Missing-topic result:', missing['type'], missing.get('reason'))
    assert missing['type'] == 'refusal' and missing['reason'] == 'no_evidence'
    # Keep this acceptance conversation available for UI/PDF verification; delete it in the browser test afterward.
    output = {'conversation_id': cid, 'result': result, 'receipt_verification': receipt, 'followup': followup,
              'broad_phrasing': broad, 'out_of_domain': out, 'missing_topic': missing}
    (root / 'eval/results/live-acceptance.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print('Live acceptance results saved without secrets.')
