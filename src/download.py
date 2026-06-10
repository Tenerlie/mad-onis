from __future__ import annotations
import base64,logging,mimetypes,re
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
log=logging.getLogger(__name__)
_FETCH_JS="\nasync (url) => {\n  const resp = await fetch(url, { credentials: 'include' });\n  const buf = await resp.arrayBuffer();\n  const bytes = new Uint8Array(buf);\n  let binary = '';\n  const chunk = 0x8000;\n  for (let i = 0; i < bytes.length; i += chunk) {\n    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));\n  }\n  return {\n    status: resp.status,\n    contentDisposition: resp.headers.get('content-disposition'),\n    contentType: resp.headers.get('content-type'),\n    bodyB64: btoa(binary),\n  };\n}\n"
@dataclass
class DownloadResult:doc_id:str;url:str;ext_n:int;status:int;ok:bool;path:Path|None=None;size:int=0;error:str|None=None
def filename_from_headers(content_disposition:str|None,content_type:str|None,doc_id:str)->str:
	if content_disposition:
		msg=Message();msg['content-disposition']=content_disposition;name=msg.get_filename()
		if name:return _sanitize(name)
	ext=_guess_extension(content_type);return _sanitize(f"{doc_id}{ext}")
def _guess_extension(content_type:str|None)->str:
	if not content_type:return''
	mime=content_type.split(';',1)[0].strip();return mimetypes.guess_extension(mime)or''
_WIN_RESERVED={'con','prn','aux','nul',*(f"com{i}"for i in range(1,10)),*(f"lpt{i}"for i in range(1,10))}
def _sanitize(name:str)->str:
	name=name.replace('\\','/').split('/')[-1].strip();name=re.sub('[\\x00-\\x1f<>:"|?*]','_',name);name=name.rstrip(' .')
	if name.split('.',1)[0].lower()in _WIN_RESERVED:name=f"_{name}"
	return name or'download'
def _unique_path(directory:Path,filename:str,used:set[str])->Path:
	candidate=filename
	if candidate in used:
		stem,dot,ext=filename.partition('.');i=1
		while candidate in used:candidate=f"{stem}_{i}{dot}{ext}"if dot else f"{stem}_{i}";i+=1
	used.add(candidate);return directory/candidate
async def download_documents(page,config,ids:list[str],ext_base:int)->list[DownloadResult]:
	out_dir=config.output_dir;out_dir.mkdir(parents=True,exist_ok=True);results:list[DownloadResult]=[];used_names:set[str]=set()
	for(i,doc_id)in enumerate(ids):
		ext_n=ext_base+1+i;url=config.dms_url(doc_id,ext_n);log.info('Downloading [%d/%d] id=%s ext-%d url=%s',i+1,len(ids),doc_id,ext_n,url)
		try:resp=await page.evaluate(_FETCH_JS,url)
		except Exception as exc:log.error('Fetch failed for %s: %s',doc_id,exc);results.append(DownloadResult(doc_id,url,ext_n,0,False,error=str(exc)));continue
		status=int(resp.get('status',0))
		if status!=200:log.error('Non-200 (%d) for %s; skipping',status,doc_id);results.append(DownloadResult(doc_id,url,ext_n,status,False,error=f"HTTP {status}"));continue
		body=base64.b64decode(resp.get('bodyB64',''));filename=filename_from_headers(resp.get('contentDisposition'),resp.get('contentType'),doc_id);dest=_unique_path(out_dir,filename,used_names);dest.write_bytes(body);log.info('Saved %s (%d bytes) -> %s',filename,len(body),dest);results.append(DownloadResult(doc_id,url,ext_n,status,True,path=dest,size=len(body)))
	return results