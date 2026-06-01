import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WEBUI_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = SCRIPT_DIR / "data"
WILDCARDS_DIR = SCRIPT_DIR.parent / "sd-dynamic-prompts" / "wildcards"

DEFAULT_CONFIG = {
    "genPrompt": "genPrompt.json",
    "genPara": "genPara.json",
    "prompts": "prompts.json",
    "process": "process.json",
    "api_url": "http://127.0.0.1:7860",
    "wildcards": str(WILDCARDS_DIR),
    "output_dir": str(WEBUI_ROOT / "outputs" / "sd-dynamic-helper"),
}


class Config:
    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        config_path = DATA_DIR / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            for k, v in user_cfg.items():
                if v:
                    self._data[k] = v

    def _resolve(self, key):
        val = self._data.get(key, "")
        if not val:
            return None
        p = Path(val)
        if not p.is_absolute():
            p = DATA_DIR / p
        return p

    @property
    def gen_prompt_path(self):
        return self._resolve("genPrompt")

    @property
    def gen_para_path(self):
        return self._resolve("genPara")

    @property
    def prompts_path(self):
        return self._resolve("prompts")

    @property
    def process_path(self):
        return self._resolve("process")

    @property
    def api_url(self):
        return self._data.get("api_url", DEFAULT_CONFIG["api_url"])

    @property
    def wildcards_path(self):
        val = self._data.get("wildcards", "")
        if val:
            p = Path(val)
            if p.is_absolute():
                return p
            return SCRIPT_DIR / p
        return WILDCARDS_DIR

    @property
    def webui_root(self):
        return WEBUI_ROOT

    @property
    def output_dir(self):
        val = self._data.get("output_dir", "")
        if val:
            p = Path(val)
            if p.is_absolute():
                return p
            return SCRIPT_DIR / p
        return WEBUI_ROOT / "outputs" / "sd-dynamic-helper"
