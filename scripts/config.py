import json
import sys
from pathlib import Path

# PyInstaller 打包后：代码在 sys._MEIPASS，数据在 exe 所在目录
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys._MEIPASS).resolve() / "scripts"
    PROJ_DIR = Path(sys.executable).resolve().parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent
    PROJ_DIR = SCRIPT_DIR.parent

WEBUI_ROOT = PROJ_DIR.parent.parent
DATA_DIR = PROJ_DIR / "data"
WILDCARDS_DIR = PROJ_DIR.parent / "sd-dynamic-prompts" / "wildcards"

DEFAULT_CONFIG = {
    "genPrompt": "genPrompt.json",
    "genPara": "genPara.json",
    "prompts": "prompts.json",
    "process": "process.json",
    "api_url": "http://127.0.0.1:7860",
    "webui" : str(WEBUI_ROOT),
    "wildcards": str(WILDCARDS_DIR),
    # 生图后把图片元数据中的 Template / Negative Template 改为 genPrompt.json 模板内容
    "fix_pnginfo": True,
}


class Config:
    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        # 当前加载的 config.json 路径（用于 $$ 前缀相对路径解析）
        self._config_path: Path | None = None
        self._load()

    def _load(self):
        self.load_from_path(DATA_DIR / "config.json")

    def load_from_path(self, path: str | Path):
        """从指定路径加载 JSON 配置并完全替换当前设置。"""
        p = Path(path)
        if not p.exists():
            return
        self._config_path = p.resolve()
        # 重置为默认值，再用文件内容覆盖（不在文件中的键保留默认值）
        self._data = dict(DEFAULT_CONFIG)
        with open(p, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        for k, v in user_cfg.items():
            if k == "fix_pnginfo":
                # 布尔开关允许显式关闭
                self._data[k] = bool(v)
                continue
            if v:
                self._data[k] = v

    def _resolve(self, key):
        """解析配置中的路径。

        - 绝对路径：原样使用
        - `$$` 前缀：以 **config.json 所在目录** 为基准（如
          "$$../genPrompt.json" = config.json 所在目录的上一级/genPrompt.json）
        - 其他相对路径：以项目根 (PROJ_DIR) 为基准（原有行为）
        """
        val = self._data.get(key, "")
        if not val:
            return None
        if val.startswith("$$"):
            base = self._config_path.parent if self._config_path else PROJ_DIR
            rel = val[2:].lstrip("/\\")
            if not rel:
                return base
            return (base / rel).resolve()
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
        return self._resolve("webui")

    @property
    def fix_pnginfo(self):
        """生图后是否把图片元数据中的模板信息改为 genPrompt.json 内容。"""
        return bool(self._data.get("fix_pnginfo", True))

    @property
    def proj_dir(self):
        return PROJ_DIR
