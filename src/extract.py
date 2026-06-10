from __future__ import annotations
import logging,re
log=logging.getLogger(__name__)
UUID_RE=re.compile('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',re.IGNORECASE)
def _as_list(value)->list:
	if value is None:return[]
	if isinstance(value,list):return value
	return[value]
def _get(node,key:str)->list:
	if not isinstance(node,dict):return[]
	return _as_list(node.get(key))
def extract_document_ids(payload:dict)->list[str]:
	ids:list[str]=[];seen:set[str]=set()
	for tile in _as_list(payload.get('initialTileData')if isinstance(payload,dict)else None):
		for element in _get(tile,'elements'):
			for attr in _get(element,'attrs'):
				for ref in _get(attr,'refs'):
					for doc in _get(ref,'RC_REFERENCED_DOCUMENTS'):
						for artefact in _get(doc,'artefactKey'):
							raw_id=artefact.get('id')if isinstance(artefact,dict)else None
							if not isinstance(raw_id,str)or not UUID_RE.match(raw_id):continue
							if raw_id not in seen:seen.add(raw_id);ids.append(raw_id)
	if not ids:top_keys=list(payload.keys())if isinstance(payload,dict)else type(payload).__name__;log.warning('No document ids found on the confirmed path. Top-level keys seen: %s',top_keys)
	else:log.info('Extracted %d document id(s): %s',len(ids),ids)
	return ids