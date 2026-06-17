from __future__ import annotations
import base64,logging,mimetypes,re
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from urllib.parse import unquote
from src import db
from src.extract import DocumentRef
log=logging.getLogger(__name__)
_FETCH_JS="\nasync (url) => {\n  const resp = await fetch(url, { credentials: 'include' });\n  const buf = await resp.arrayBuffer();\n  const bytes = new Uint8Array(buf);\n  let binary = '';\n  const chunk = 0x8000;\n  for (let i = 0; i < bytes.length; i += chunk) {\n    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));\n  }\n  return {\n    status: resp.status,\n    contentDisposition: resp.headers.get('content-disposition'),\n    contentType: resp.headers.get('content-type'),\n    bodyB64: btoa(binary),\n  };\n}\n"
@dataclass
class DownloadResult:doc_id:str;url:str;ext_n:int;status:int;ok:bool;path:Path|None=None;size:int=0;error:str|None=None
def filename_from_headers(content_disposition:str|None,content_type:str|None,doc_id:str)->str:
	if content_disposition:
		msg=Message();msg['content-disposition']=content_disposition;name=msg.get_filename()
		if name:return _sanitize(name)
	ext=_guess_extension(content_type);return _sanitize(f"{doc_id}{ext}")
def resolve_filename(ref,content_disposition:str|None,content_type:str|None,doc_id:str)->str:
	name=getattr(ref,'name',None)
	if not name:return filename_from_headers(content_disposition,content_type,doc_id)
	clean=_sanitize(unquote(name));ext=_cd_extension(content_disposition)or _guess_extension(content_type)
	if ext and not clean.lower().endswith(ext.lower()):clean=_sanitize(f"{clean}{ext}")
	return clean
def _cd_extension(content_disposition:str|None)->str:
	if not content_disposition:return''
	msg=Message();msg['content-disposition']=content_disposition;name=msg.get_filename();return Path(unquote(name)).suffix if name else''
def _guess_extension(content_type:str|None)->str:
	if not content_type:return''
	mime=content_type.split(';',1)[0].strip();return mimetypes.guess_extension(mime)or''
_WIN_RESERVED={'con','prn','aux','nul',*(f"com{i}"for i in range(1,10)),*(f"lpt{i}"for i in range(1,10))}
def _sanitize(name:str)->str:
	name=name.replace('\\','/').split('/')[-1].strip();name=re.sub('[\\x00-\\x1f<>:"|?*]','_',name);name=name.rstrip(' .')
	if name.split('.',1)[0].lower()in _WIN_RESERVED:name=f"_{name}"
	return name or'download'
def _unique_path(directory:Path,filename:str,used:set[str])->Path:
	def taken(name:str)->bool:return name in used or(directory/name).exists()
	candidate=filename
	if taken(candidate):
		stem,dot,ext=filename.partition('.');i=1
		while taken(candidate):candidate=f"{stem}_{i}{dot}{ext}"if dot else f"{stem}_{i}";i+=1
	used.add(candidate);return directory/candidate
def repair_filenames(config,conn)->tuple[int,int]:
	out_dir=config.output_dir;renamed=correct=0;used:dict[Path,set[str]]={}
	for row in db.done_rows(conn):
		relpath=row['relpath']
		if not relpath:continue
		old=out_dir/relpath
		if not old.exists():log.warning('Recorded file missing, skipping repair: %s',relpath);continue
		ref=DocumentRef(row['doc_id'],row['name'],row['folder']);new_name=resolve_filename(ref,None,row['content_type'],row['doc_id'])
		if new_name==old.name:correct+=1;continue
		dest=_unique_path(old.parent,new_name,used.setdefault(old.parent,set()));old.rename(dest);new_rel=dest.relative_to(out_dir).as_posix();db.set_saved(conn,row['doc_id'],dest.name,new_rel);log.info('Repaired %s -> %s',relpath,new_rel);renamed+=1
	return renamed,correct
async def download_documents(page,config,conn,items,ext_base:int)->list[DownloadResult]:
	out_dir=config.output_dir;out_dir.mkdir(parents=True,exist_ok=True);results:list[DownloadResult]=[];used_names:dict[Path,set[str]]={};total=len(items)
	for(n,(orig_index,ref))in enumerate(items):
		doc_id=ref.doc_id;ext_n=ext_base+1+orig_index;url=config.dms_url(doc_id,ext_n);log.info('Downloading [%d/%d] id=%s ext-%d url=%s',n+1,total,doc_id,ext_n,url)
		try:resp=await page.evaluate(_FETCH_JS,url)
		except Exception as exc:log.error('Fetch failed for %s: %s',doc_id,exc);db.mark_failed(conn,doc_id,str(exc));results.append(DownloadResult(doc_id,url,ext_n,0,False,error=str(exc)));continue
		status=int(resp.get('status',0))
		if status!=200:log.error('Non-200 (%d) for %s; skipping',status,doc_id);db.mark_failed(conn,doc_id,f"HTTP {status}");results.append(DownloadResult(doc_id,url,ext_n,status,False,error=f"HTTP {status}"));continue
		body=base64.b64decode(resp.get('bodyB64',''));content_type=resp.get('contentType');filename=resolve_filename(ref,resp.get('contentDisposition'),content_type,doc_id);dest_dir=out_dir/_sanitize(ref.folder)if ref.folder else out_dir;dest_dir.mkdir(parents=True,exist_ok=True);dest=_unique_path(dest_dir,filename,used_names.setdefault(dest_dir,set()));dest.write_bytes(body);relpath=dest.relative_to(out_dir).as_posix();log.info('Saved %s (%d bytes) -> %s',relpath,len(body),dest);db.mark_done(conn,doc_id,filename=dest.name,relpath=relpath,size=len(body),content_type=content_type);results.append(DownloadResult(doc_id,url,ext_n,status,True,path=dest,size=len(body)))
	return results