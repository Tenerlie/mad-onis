from __future__ import annotations
import logging,re
from dataclasses import dataclass
log=logging.getLogger(__name__)
@dataclass(frozen=True)
class DocumentRef:doc_id:str;name:str|None;folder:str|None
UUID_RE=re.compile('^\\s*\\{?\\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\\s*\\}?\\s*$',re.IGNORECASE)
def _normalize_id(raw)->str|None:
	if not isinstance(raw,str):return
	match=UUID_RE.match(raw);return match.group(1).lower()if match else None
def _as_list(value)->list:
	if value is None:return[]
	if isinstance(value,list):return value
	return[value]
def _get(node,key:str)->list:
	if not isinstance(node,dict):return[]
	return _as_list(node.get(key))
def _clean_str(value)->str|None:
	if not isinstance(value,str):return
	value=value.strip();return value or None
def extract_document_refs(payload:dict)->list[DocumentRef]:
	refs:list[DocumentRef]=[];seen:set[str]=set();tile_data=[]
	for status in _get(payload,'modelStatus'):tile_data.extend(_get(status,'initialTileData'))
	if not tile_data and isinstance(payload,dict):tile_data=_as_list(payload.get('initialTileData'))
	for tile in tile_data:
		for element in _get(tile,'elements'):
			folder=_clean_str(element.get('name'))if isinstance(element,dict)else None
			for ref in _get(element,'refs'):
				for doc in _get(ref,'RC_REFERENCED_DOCUMENTS'):
					for artefact in _get(doc,'artefactKey'):
						if not isinstance(artefact,dict):continue
						doc_id=_normalize_id(artefact.get('id'))
						if doc_id is None or doc_id in seen:continue
						seen.add(doc_id);refs.append(DocumentRef(doc_id=doc_id,name=_clean_str(artefact.get('name')),folder=folder))
	if not refs:top_keys=list(payload.keys())if isinstance(payload,dict)else type(payload).__name__;log.warning('No document refs found on the verified path. Top-level keys seen: %s',top_keys)
	else:log.info('Extracted %d document ref(s): %s',len(refs),[r.doc_id for r in refs])
	return refs