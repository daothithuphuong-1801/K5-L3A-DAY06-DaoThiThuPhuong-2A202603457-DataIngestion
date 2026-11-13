"""Run with: python -m src.run --manifest data/manifest.json --benchmark benchmark/questions.json"""
import argparse
import csv
import json
import logging
import os
import platform
import time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from .chunking import fixed_size,by_paragraph
from .embeddings import MyEmbedder
from .evaluation import evaluate_query,summarize
from .ingestion import load_pdf
from .store import PgVectorStore

LOG=logging.getLogger(__name__)

def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save_json(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def validate_questions(questions,documents):
    if len(questions)<20:raise ValueError('Benchmark must have >=20 questions')
    if len({q['id'] for q in questions})!=len(questions):raise ValueError('Duplicate question IDs')
    counts=Counter(q['split'] for q in questions)
    if counts['dev']<15 or counts['test']<5 or sum(counts.values())!=len(questions):raise ValueError('Need >=15 dev, >=5 test')
    if sum(bool(q.get('filter')) for q in questions)<3 or not any(q['split']=='test' and q.get('filter') for q in questions):
        raise ValueError('Need >=3 filter questions, including >=1 test')
    lookup={(p.document_id,p.page):p.text for p in documents}
    for q in questions:
        for field in ('id','split','question','expected_answer','gold_source_id','gold_page','evidence_quote'):
            if field not in q or q[field] in (None,''):raise ValueError(f'Missing {field} in {q.get("id")}')
        golds=q.get('gold_alternatives') or [q]
        for gold in golds:
            text=lookup.get((gold['gold_source_id'],int(gold['gold_page'])))
            if not text or ' '.join(gold['evidence_quote'].split()).casefold() not in ' '.join(text.split()).casefold():
                raise ValueError(f'Unverified evidence: {q["id"]} at {gold["gold_source_id"]}:{gold["gold_page"]}')

def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='data/manifest.json')
    parser.add_argument('--benchmark',default='benchmark/questions.json')
    parser.add_argument('--results',default='results')
    parser.add_argument('--model',default='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    parser.add_argument('--fixed-size',type=int,default=500)
    parser.add_argument('--overlap',type=int,default=50)
    parser.add_argument('--paragraph-size',type=int,default=500)
    args=parser.parse_args()
    output=Path(args.results);output.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[logging.StreamHandler(),logging.FileHandler(output/'errors.log',encoding='utf-8')],format='%(asctime)s %(levelname)s %(message)s')
    manifest=read_json(args.manifest)
    if not isinstance(manifest,list) or not manifest:raise ValueError('Manifest must be a nonempty list')
    pages=[]
    for doc in manifest:
        for required in ('source_id','title','source_path_or_url','license_or_permission','accessed_at','content_pages','metadata'):
            if required not in doc:raise ValueError(f'Missing manifest field {required}')
        path=Path(doc['source_path_or_url'])
        if not path.exists():raise FileNotFoundError(f'Missing corpus PDF: {path}')
        extracted=load_pdf(path,doc['source_id'],doc['source_path_or_url'])
        by_id={p.page:p for p in extracted}
        for number in doc['content_pages']:
            page=by_id.get(int(number))
            if page is None or not page.text:raise ValueError(f'Invalid content page {doc["source_id"]}:{number}')
            page.metadata=dict(doc['metadata'])
            matches=[entry['section'] for entry in doc.get('page_sections',[]) if int(entry['start_page'])<=page.page<=int(entry['end_page'])]
            if len(matches)!=1:raise ValueError(f'Page {page.page} must map to exactly one verified section')
            page.metadata['section']=matches[0]
            pages.append(page)
    if len({(p.document_id,p.page) for p in pages})<30:raise ValueError('Corpus has fewer than 30 useful content pages')
    questions=read_json(args.benchmark)
    validate_questions(questions,pages)
    model=MyEmbedder(args.model)
    url=os.getenv('DATABASE_URL')
    if not url:raise RuntimeError('DATABASE_URL missing; configure .env')
    store=PgVectorStore(url,model.dimensions);store.create_schema()
    strategies={'A':[c for p in pages for c in fixed_size(p,args.fixed_size,args.overlap)],
                'B':[c for p in pages for c in by_paragraph(p,args.paragraph_size)]}
    strategies['C']=strategies['B']
    stats={};traces=[]
    for strategy,chunks in strategies.items():
        start=time.perf_counter()
        vectors=model.embed_documents([c.text for c in chunks])
        store.upsert(strategy,chunks,vectors)
        stats[strategy]={'chunk_count':len(chunks),'total_characters':sum(len(c.text) for c in chunks),
                         'min_chunk_length':min(map(lambda c:len(c.text),chunks)),
                         'max_chunk_length':max(map(lambda c:len(c.text),chunks)),
                         'ingest_seconds':round(time.perf_counter()-start,3),'api_cost_usd':0}
        for q in questions:
            vec=model.embed_query(q['question'])
            # Only C filters, and only when the question explicitly supplies filter.
            hits=store.search(strategy,vec,top_k=3,filters=q.get('filter') if strategy=='C' else None)
            trace=evaluate_query(q,hits);trace['strategy']=strategy;traces.append(trace)
    save_json(output/'retrieval_trace.json',traces)
    metrics=summarize(traces);save_json(output/'metrics.json',metrics)
    save_json(output/'run_info.json',{'utc_time':datetime.now(timezone.utc).isoformat(),
        'python':platform.python_version(),'model':args.model,'dimensions':model.dimensions,
        'vector_store':'PostgreSQL + pgvector, exact cosine','strategies':stats,
        'note':'Human coherence, metadata correctness and grounding labels must be audited separately.'})
    with (output/'metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['strategy','split','hit1_n','hit3_n','N','hit1','hit3','chunks','ingest_seconds','api_cost_usd'])
        for key,m in metrics.items():
            strategy,split=key.split('_');s=stats[strategy]
            writer.writerow([strategy,split,m['hit1_n'],m['hit3_n'],m['n'],m['hit1'],m['hit3'],s['chunk_count'],s['ingest_seconds'],s['api_cost_usd']])
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
