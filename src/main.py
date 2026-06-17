from __future__ import annotations
import argparse,asyncio,dataclasses,logging,sys
from src import db
from src.browser import ReaderSession
from src.config import load_config
from src.download import download_documents,repair_filenames
from src.extract import extract_document_refs
from src.logging_setup import setup_logging
log=logging.getLogger('madonis')
async def run(config,dry_run:bool,ncap:int|None)->int:
	conn=db.connect(config.db_path)
	try:
		async with ReaderSession(config)as session:
			await session.navigate();await session.click_target();payload=await session.wait_for_open_with_editor();refs=extract_document_refs(payload)
			if not refs:log.error('No document refs extracted; nothing to download.');return 1
			db.record_seen(conn,refs);todo=[(i,ref)for(i,ref)in enumerate(refs)if db.needs_download(conn,ref,config.output_dir)];skipped=len(refs)-len(todo)
			if ncap is not None and len(todo)>ncap:log.info('Capping this run to %d of %d pending document(s).',ncap,len(todo));todo=todo[:ncap]
			ext_base=await session.read_ext_base()
			if dry_run:
				for(_,ref)in todo:url=config.dms_url(ref.doc_id,ext_base+1);log.info('[dry-run] would download id=%s name=%r folder=%r -> %s',ref.doc_id,ref.name,ref.folder,url)
				log.info('[dry-run] %d to download, %d already done. No DB/disk writes.',len(todo),skipped);return 0
			results=await download_documents(session.page,config,conn,todo,ext_base)
	finally:conn.close()
	ok=sum(1 for r in results if r.ok);failed=len(results)-ok;remaining=len(refs)-skipped-ok;log.info('Done: %d downloaded, %d failed, %d already done, %d remaining (output: %s)',ok,failed,skipped,remaining,config.output_dir);return 0 if failed==0 else 2
def main(argv:list[str]|None=None)->int:
	parser=argparse.ArgumentParser(description='Rescue documents from the canvas app.');parser.add_argument('--config',default=None,help='Path to config.toml (defaults to project root).');parser.add_argument('--dry-run',action='store_true',help='Capture + build URLs but do not download.');parser.add_argument('--headed',action='store_true',help='Launch a visible browser window for debugging (overrides config headless).');parser.add_argument('--slow-mo',type=float,default=None,metavar='MS',help='Slow each browser action by MS milliseconds so you can watch it (e.g. 500).');parser.add_argument('--ncap',type=int,default=None,metavar='N',help='Cap new downloads per run to N (default: uncapped). Remaining docs go next run.');parser.add_argument('--repair-names',action='store_true',help='Offline: rename already-downloaded files to fix extensions (no browser, no re-download).');args=parser.parse_args(argv);config=load_config(args.config);config=_apply_browser_overrides(config,args);log_file=setup_logging();log.info('Config loaded: base_url=%s output_dir=%s dry_run=%s',config.base_url,config.output_dir,args.dry_run)
	if args.repair_names:
		conn=db.connect(config.db_path)
		try:renamed,correct=repair_filenames(config,conn)
		finally:conn.close()
		log.info('Repair complete: %d renamed, %d already correct.',renamed,correct);return 0
	try:return asyncio.run(run(config,args.dry_run,args.ncap))
	except Exception as exc:log.exception('Run failed: %s',exc);return 1
	finally:log.info('Log written to %s',log_file)
def _apply_browser_overrides(config,args):
	changes:dict={}
	if args.headed:changes['headless']=False
	if args.slow_mo is not None:changes['slow_mo_ms']=args.slow_mo
	elif args.headed and config.browser.slow_mo_ms==0:changes['slow_mo_ms']=250
	if not changes:return config
	new_browser=dataclasses.replace(config.browser,**changes);return dataclasses.replace(config,browser=new_browser)
if __name__=='__main__':sys.exit(main())