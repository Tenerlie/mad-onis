from __future__ import annotations
import logging,sqlite3
from datetime import datetime,timezone
from pathlib import Path
log=logging.getLogger(__name__)
_SCHEMA="\nCREATE TABLE IF NOT EXISTS documents (\n    doc_id       TEXT PRIMARY KEY,\n    name         TEXT,\n    folder       TEXT,\n    filename     TEXT,\n    relpath      TEXT,\n    size         INTEGER,\n    content_type TEXT,\n    status       TEXT NOT NULL DEFAULT 'pending',\n    error        TEXT,\n    attempts     INTEGER NOT NULL DEFAULT 0,\n    first_seen   TEXT,\n    updated_at   TEXT\n);\n"
def _now()->str:return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect(path:str|Path)->sqlite3.Connection:path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row;conn.execute(_SCHEMA);conn.commit();log.info('State DB: %s',path);return conn
def record_seen(conn:sqlite3.Connection,refs)->None:
	now=_now()
	for ref in refs:conn.execute("\n            INSERT INTO documents (doc_id, name, folder, status, first_seen, updated_at)\n            VALUES (?, ?, ?, 'pending', ?, ?)\n            ON CONFLICT(doc_id) DO UPDATE SET\n                name = excluded.name,\n                folder = excluded.folder,\n                updated_at = excluded.updated_at\n            ",(ref.doc_id,ref.name,ref.folder,now,now))
	conn.commit()
def needs_download(conn:sqlite3.Connection,ref,output_dir:Path)->bool:
	row=conn.execute('SELECT status, relpath FROM documents WHERE doc_id = ?',(ref.doc_id,)).fetchone()
	if row is None or row['status']!='done':return True
	relpath=row['relpath']
	if not relpath:return True
	return not(output_dir/relpath).exists()
def mark_done(conn:sqlite3.Connection,doc_id:str,*,filename:str,relpath:str,size:int,content_type:str|None)->None:conn.execute("\n        UPDATE documents\n        SET status = 'done', filename = ?, relpath = ?, size = ?, content_type = ?,\n            error = NULL, attempts = attempts + 1, updated_at = ?\n        WHERE doc_id = ?\n        ",(filename,relpath,size,content_type,_now(),doc_id));conn.commit()
def mark_failed(conn:sqlite3.Connection,doc_id:str,error:str)->None:conn.execute("\n        UPDATE documents\n        SET status = 'failed', error = ?, attempts = attempts + 1, updated_at = ?\n        WHERE doc_id = ?\n        ",(error,_now(),doc_id));conn.commit()
def counts(conn:sqlite3.Connection)->dict[str,int]:rows=conn.execute('SELECT status, COUNT(*) AS n FROM documents GROUP BY status').fetchall();return{row['status']:row['n']for row in rows}