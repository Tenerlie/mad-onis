from __future__ import annotations
import argparse,asyncio,dataclasses,logging,sys
from src.browser import ReaderSession
from src.config import load_config
from src.download import download_documents
from src.extract import extract_document_ids
from src.logging_setup import setup_logging
log=logging.getLogger('madonis')
async def run(config,dry_run:bool)->int:
	async with ReaderSession(config)as session:
		await session.navigate();await session.click_target();payload=await session.wait_for_open_with_editor();ids=extract_document_ids(payload)
		if not ids:log.error('No document ids extracted; nothing to download.');return 1
		ext_base=await session.read_ext_base()
		if dry_run:
			for(i,doc_id)in enumerate(ids):url=config.dms_url(doc_id,ext_base+1+i);log.info('[dry-run] would download id=%s -> %s',doc_id,url)
			log.info('[dry-run] %d document(s) would be downloaded.',len(ids));return 0
		results=await download_documents(session.page,config,ids,ext_base);ok=sum(1 for r in results if r.ok);failed=len(results)-ok;log.info('Done: %d/%d downloaded, %d failed (output: %s)',ok,len(results),failed,config.output_dir);return 0 if failed==0 else 2
def main(argv:list[str]|None=None)->int:
	parser=argparse.ArgumentParser(description='Rescue documents from the canvas app.');parser.add_argument('--config',default=None,help='Path to config.toml (defaults to project root).');parser.add_argument('--dry-run',action='store_true',help='Capture + build URLs but do not download.');parser.add_argument('--headed',action='store_true',help='Launch a visible browser window for debugging (overrides config headless).');parser.add_argument('--slow-mo',type=float,default=None,metavar='MS',help='Slow each browser action by MS milliseconds so you can watch it (e.g. 500).');args=parser.parse_args(argv);config=load_config(args.config);config=_apply_browser_overrides(config,args);log_file=setup_logging();log.info('Config loaded: base_url=%s output_dir=%s dry_run=%s',config.base_url,config.output_dir,args.dry_run)
	try:return asyncio.run(run(config,args.dry_run))
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