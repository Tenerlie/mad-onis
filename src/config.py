from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path
DEFAULT_CONFIG_PATH=Path(__file__).resolve().parent.parent/'config.toml'
@dataclass(frozen=True)
class ReaderConfig:path:str;click_x:int;click_y:int;load_wait_s:float
@dataclass(frozen=True)
class NetworkConfig:nav_timeout_s:float;response_timeout_s:float;download_lang:str
@dataclass(frozen=True)
class BrowserConfig:viewport_width:int;viewport_height:int;device_scale:float;channel:str;executable_path:str;headless:bool;slow_mo_ms:float
@dataclass(frozen=True)
class Config:
	base_url:str;output_dir:Path;reader:ReaderConfig;network:NetworkConfig;browser:BrowserConfig
	def dms_url(self,doc_id:str,ext_n:int)->str:return f"{self.base_url}/dms/{doc_id}?_dc=ext-{ext_n}&lang={self.network.download_lang}&media=false&type=0"
	@property
	def reader_url(self)->str:return f"{self.base_url}{self.reader.path}"
def load_config(path:str|Path|None=None)->Config:
	cfg_path=Path(path)if path else DEFAULT_CONFIG_PATH
	if not cfg_path.is_file():raise FileNotFoundError(f"Config file not found: {cfg_path}")
	with cfg_path.open('rb')as fh:
		try:raw=tomllib.load(fh)
		except tomllib.TOMLDecodeError as exc:raise ValueError(f"Could not parse {cfg_path}: {exc}\nIf a path contains backslashes (e.g. a Windows path), wrap it in single quotes so it is a TOML literal string, e.g. output_dir = 'C:\\Users\\Operator\\Downloads', or use forward slashes.")from exc
	base_url=_require(raw,'base_url').rstrip('/');output_dir=Path(_require(raw,'output_dir'));reader_raw=raw.get('reader',{});network_raw=raw.get('network',{});browser_raw=raw.get('browser',{});reader=ReaderConfig(path=reader_raw.get('path','/main.view?reader=Reader#0'),click_x=int(reader_raw.get('click_x',469)),click_y=int(reader_raw.get('click_y',303)),load_wait_s=float(reader_raw.get('load_wait_s',10)));network=NetworkConfig(nav_timeout_s=float(network_raw.get('nav_timeout_s',30)),response_timeout_s=float(network_raw.get('response_timeout_s',30)),download_lang=str(network_raw.get('download_lang','pl')));browser=BrowserConfig(viewport_width=int(browser_raw.get('viewport_width',1920)),viewport_height=int(browser_raw.get('viewport_height',600)),device_scale=float(browser_raw.get('device_scale',1)),channel=str(browser_raw.get('channel','')).strip(),executable_path=str(browser_raw.get('executable_path','')).strip(),headless=bool(browser_raw.get('headless',True)),slow_mo_ms=float(browser_raw.get('slow_mo_ms',0)));return Config(base_url=base_url,output_dir=output_dir,reader=reader,network=network,browser=browser)
def _require(raw:dict,key:str):
	if key not in raw or raw[key]in(None,''):raise ValueError(f"Missing required config key: '{key}'")
	return raw[key]