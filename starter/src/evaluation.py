"""Strict evidence retrieval metrics; manual judgments remain manual."""
import re
import unicodedata
from collections import defaultdict
from typing import Any

def _norm(s):
    return ' '.join(unicodedata.normalize('NFC',str(s)).casefold().split())

def _golds(q):
    # Supports one gold or multiple explicitly verified alternatives.
    return q.get('gold_alternatives') or [{'gold_source_id':q['gold_source_id'],
                                          'gold_page':q['gold_page'],
                                          'evidence_quote':q['evidence_quote']}]

def evaluate_query(question:dict[str,Any],hits:list[dict[str,Any]])->dict[str,Any]:
    evidence=[]
    for hit in hits[:3]:
        match=any(str(hit.get('document_id'))==str(g['gold_source_id'])
                  and str(hit.get('page'))==str(g['gold_page'])
                  and _norm(g['evidence_quote']) in _norm(hit.get('text',''))
                  for g in _golds(question))
        evidence.append(match)
    return {'id':question['id'],'split':question['split'],'question':question['question'],
            'filter':question.get('filter'),'hit1':int(bool(evidence and evidence[0])),
            'hit3':int(any(evidence)),'evidence_matches':evidence,'hits':hits[:3],
            'gold':_golds(question),
            'note':'Exact evidence proxy; equivalent evidence requires human verification.'}

def summarize(traces:list[dict[str,Any]])->dict[str,Any]:
    groups=defaultdict(list)
    for t in traces:groups[(t['strategy'],t['split'])].append(t)
    return {f'{strategy}_{split}':{'n':len(rows),'hit1_n':sum(r['hit1'] for r in rows),
                                   'hit3_n':sum(r['hit3'] for r in rows),
                                   'hit1':sum(r['hit1'] for r in rows)/len(rows),
                                   'hit3':sum(r['hit3'] for r in rows)/len(rows)}
            for (strategy,split),rows in groups.items()}
