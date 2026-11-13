"""Persistent exact cosine retrieval using PostgreSQL + pgvector."""
import json
from typing import Any
from .models import Chunk

class PgVectorStore:
    def __init__(self,database_url:str,dimensions:int):
        if dimensions<=0:raise ValueError('Invalid vector dimensions')
        self.database_url=database_url;self.dimensions=dimensions
    def create_schema(self)->None:
        import psycopg
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
                cur.execute(f'''CREATE TABLE IF NOT EXISTS ingestion_chunks (
                    strategy TEXT NOT NULL, chunk_id TEXT NOT NULL, document_id TEXT NOT NULL,
                    source TEXT NOT NULL, page INTEGER NOT NULL, content TEXT NOT NULL,
                    metadata JSONB NOT NULL, embedding vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY(strategy,chunk_id))''')
                cur.execute('CREATE INDEX IF NOT EXISTS ingestion_metadata_idx ON ingestion_chunks USING gin(metadata)')
                cur.execute('CREATE INDEX IF NOT EXISTS ingestion_doc_idx ON ingestion_chunks(strategy,document_id)')
    def upsert(self,strategy:str,chunks:list[Chunk],vectors:list[list[float]])->None:
        import psycopg
        if len(chunks)!=len(vectors):raise ValueError('Chunk/vector count mismatch')
        if any(len(v)!=self.dimensions for v in vectors):raise ValueError('Embedding dimensions mismatch')
        if strategy not in ('A','B','C'):raise ValueError('Invalid strategy')
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Snapshot semantics: delete stale chunks and refresh all current chunks.
                cur.execute('DELETE FROM ingestion_chunks WHERE strategy=%s',(strategy,))
                for chunk,vec in zip(chunks,vectors):
                    cur.execute('''INSERT INTO ingestion_chunks
                        (strategy,chunk_id,document_id,source,page,content,metadata,embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector)''',
                        (strategy,chunk.chunk_id,chunk.document_id,chunk.source,chunk.page,
                         chunk.text,json.dumps(chunk.metadata,ensure_ascii=False),
                         '['+','.join(str(float(x)) for x in vec)+']'))
    def search(self,strategy:str,query_vector:list[float],top_k:int=3,filters:dict[str,Any]|None=None)->list[dict[str,Any]]:
        import psycopg
        if len(query_vector)!=self.dimensions:raise ValueError('Query dimensions mismatch')
        if strategy not in ('A','B','C'):raise ValueError('Invalid strategy')
        if top_k<1:raise ValueError('top_k must be positive')
        # Only allow fields populated from the trusted manifest.
        allowed={'year','section','category','audience','language','version','document_type'}
        if filters and (set(filters)-allowed):raise ValueError('Unsupported filter key')
        vector='['+','.join(str(float(x)) for x in query_vector)+']'
        sql='''SELECT chunk_id,document_id,source,page,content,metadata,
                  1-(embedding <=> %s::vector) AS score
                  FROM ingestion_chunks WHERE strategy=%s'''
        params=[vector,strategy]
        if filters:
            for key,value in filters.items():
                if not isinstance(value,(str,int,float,bool)):raise ValueError('Invalid filter value')
                sql+=' AND metadata ->> %s = %s';params.extend([key,str(value).lower() if isinstance(value,bool) else str(value)])
        sql+=' ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s';params.extend([vector,top_k])
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql,params)
                rows=cur.fetchall()
        return [{'chunk_id':r[0],'document_id':r[1],'source':r[2],'page':r[3],
                 'text':r[4],'metadata':r[5], 'score':float(r[6])} for r in rows]
