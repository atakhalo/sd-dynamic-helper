import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJ_DIR = Path(__file__).resolve().parent.parent
WEBUI_ROOT = PROJ_DIR.parent.parent
DATA_DIR = PROJ_DIR / "data"
WILDCARDS_DIR = PROJ_DIR.parent / "sd-dynamic-prompts" / "wildcards"

DEFAULT_CONFIG = {
    "genPrompt": "genPrompt.json",
    "genPara": "genPara.json",
    "prompts": "prompts.json",
    "process": "process.json",
    "api_url": "http://127.0.0.1:7860",
    "wildcards": str(WILDCARDS_DIR),
}


class Config:
    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        self.load_from_path(DATA_DIR / "config.json")

    def load_from_path(self, path: str | Path):
        """从指定路径加载 JSON 配置并完全替换当前设置。"""
        p = Path(path)
        if not p.exists():
            return
        # 重置为默认值，再用文件内容覆盖（不在文件中的键保留默认值）
        self._data = dict(DEFAULT_CONFIG)
        with open(p, "r", encoding="utf-8") as f:
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
            p = PROJ_DIR / p
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
        return self._resolve("wildcards") or WILDCARDS_DIR

    @property
    def webui_root(self):
        return WEBUI_ROOT

    @property
    def proj_dir(self):
        return PROJ_DIR
