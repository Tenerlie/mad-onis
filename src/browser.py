from __future__ import annotations
import asyncio,json,logging,re
from playwright.async_api import async_playwright
log=logging.getLogger(__name__)
_SKIP_PREFIXES='image/','video/','audio/','font/','application/octet-stream'
_EXT_ID_RE=re.compile('ext-(\\d+)')
class ReaderSession:
	def __init__(self,config):self.config=config;self._pw=None;self._browser=None;self._context=None;self.page=None;(self._future):asyncio.Future|None=None
	async def __aenter__(self)->'ReaderSession':
		b=self.config.browser;launch_kwargs:dict={'headless':True}
		if b.channel:launch_kwargs['channel']=b.channel
		if b.executable_path:launch_kwargs['executable_path']=b.executable_path
		self._pw=await async_playwright().start();log.info('Launching browser (channel=%r, executable_path=%r)',b.channel,b.executable_path);self._browser=await self._pw.chromium.launch(**launch_kwargs);self._context=await self._browser.new_context(viewport={'width':b.viewport_width,'height':b.viewport_height},device_scale_factor=b.device_scale);self.page=await self._context.new_page();self._future=asyncio.get_running_loop().create_future();self.page.on('response',lambda resp:asyncio.create_task(self._on_response(resp)));return self
	async def __aexit__(self,*exc)->None:
		for closer in(self._context,self._browser):
			try:
				if closer:await closer.close()
			except Exception:pass
		if self._pw:await self._pw.stop()
	async def _on_response(self,response)->None:
		if self._future is None or self._future.done():return
		content_type=(response.headers or{}).get('content-type','')
		if content_type.startswith(_SKIP_PREFIXES):return
		try:body=await response.text()
		except Exception:return
		stripped=body.lstrip()
		if not stripped.startswith('{'):return
		try:data=json.loads(body)
		except Exception:return
		if isinstance(data,dict)and data.get('openWithEditor')is True:
			if not self._future.done():log.info('Captured openWithEditor response: %s',response.url);self._future.set_result(data)
	async def navigate(self)->None:
		url=self.config.reader_url;log.info('Navigating to %s',url);await self.page.goto(url,timeout=self.config.network.nav_timeout_s*1000)
		try:await self.page.wait_for_load_state('networkidle',timeout=self.config.reader.load_wait_s*1000)
		except Exception:pass
		log.info('Waiting %.1fs for the reader to settle',self.config.reader.load_wait_s);await asyncio.sleep(self.config.reader.load_wait_s)
	async def click_target(self)->None:x,y=self.config.reader.click_x,self.config.reader.click_y;log.info('Clicking canvas at (%d, %d)',x,y);await self.page.mouse.click(x,y)
	async def wait_for_open_with_editor(self)->dict:log.info('Waiting for openWithEditor response (timeout %.1fs)',self.config.network.response_timeout_s);return await asyncio.wait_for(self._future,timeout=self.config.network.response_timeout_s)
	async def read_ext_base(self)->int:
		raw=await self.page.evaluate("() => (typeof Ext !== 'undefined' && Ext.id) ? Ext.id() : null");log.info('Ext.id() raw output: %r',raw);match=_EXT_ID_RE.search(str(raw or''))
		if not match:raise RuntimeError(f"Could not parse an ext number from Ext.id() output: {raw!r}")
		base=int(match.group(1));log.info('Parsed ext base number: %d (downloads will start at ext-%d)',base,base+1);return base