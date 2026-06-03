import json
import logging
from pathlib import Path

from dynamicprompts.generators import CombinatorialPromptGenerator
from dynamicprompts.wildcards import WildcardManager

from scripts.config import Config

logger = logging.getLogger(__name__)


class PromptManager:
    def __init__(self, config: Config):
        self.config = config
        self.wildcard_manager = WildcardManager(
            path=str(config.wildcards_path)
        )
        self.generator = CombinatorialPromptGenerator(
            wildcard_manager=self.wildcard_manager
        )
        # 启动时从 WebUI config.json 读取一次初始值
        self._no_dedupe, self._no_sort = self._load_webui_dp_settings()
        self._apply_wildcard_settings()

    def load_gen_prompt(self):
        path = self.config.gen_prompt_path
        if not path or not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_gen_para(self):
        path = self.config.gen_para_path
        if not path or not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_webui_dp_settings(self):
        """从 WebUI config.json 读取 sd-dynamic-prompts 设置，返回 (no_dedupe, no_sort)"""
        no_dedupe = False
        no_sort = False
        webui_config_path = self.config.webui_root / "config.json"
        if not webui_config_path.exists():
            logger.warning(f"WebUI 配置文件不存在: {webui_config_path}")
            return no_dedupe, no_sort

        try:
            with open(webui_config_path, "r", encoding="utf-8") as f:
                webui_cfg = json.load(f)
            no_dedupe = webui_cfg.get("dp_wildcard_manager_no_dedupe", False)
            no_sort = webui_cfg.get("dp_wildcard_manager_no_sort", False)
            logger.info(
                "已从 WebUI 配置加载 sd-dynamic-prompts 设置: "
                f"去重={'禁用' if no_dedupe else '启用'}, "
                f"排序={'禁用' if no_sort else '启用'}"
            )
        except Exception as e:
            logger.warning(f"读取 WebUI 配置失败: {e}")
        return no_dedupe, no_sort

    def _apply_wildcard_settings(self):
        """将当前的 _no_dedupe / _no_sort 应用到 WildcardManager"""
        # sd-dynamic-prompts 插件中的逻辑：
        # dedup_wildcards = not dp_wildcard_manager_no_dedupe
        # sort_wildcards = not dp_wildcard_manager_no_sort
        self.wildcard_manager.dedup_wildcards = not self._no_dedupe
        self.wildcard_manager.sort_wildcards = not self._no_sort

    def get_webui_dp_settings(self):
        """返回当前 (no_dedupe, no_sort) 值"""
        return self._no_dedupe, self._no_sort

    def set_wildcard_settings(self, no_dedupe, no_sort):
        """由 UI 调用，更新设置并立即应用"""
        self._no_dedupe = no_dedupe
        self._no_sort = no_sort
        self._apply_wildcard_settings()
        logger.info(
            "用户手动设置 sd-dynamic-prompts: "
            f"去重={'禁用' if no_dedupe else '启用'}, "
            f"排序={'禁用' if no_sort else '启用'}"
        )

    def generate_prompts_raw(self):
        """生成提示词但不保存，返回 prompt dict 列表"""
        template_data = self.load_gen_prompt()
        if not template_data:
            raise FileNotFoundError(
                f"Cannot read {self.config.gen_prompt_path}"
            )

        raw_prompt = template_data.get("prompt", "")
        raw_negative = template_data.get("negative_prompt", "")

        prompt_results = self.generator.generate(raw_prompt)
        negative_results = self.generator.generate(raw_negative)

        if not isinstance(prompt_results, list):
            prompt_results = [prompt_results]
        if not isinstance(negative_results, list):
            negative_results = [negative_results]

        neg_count = len(negative_results)
        prompts = []
        for i, p in enumerate(prompt_results):
            n = negative_results[i % neg_count] if neg_count > 0 else ""
            prompts.append({
                "prompt": p,
                "negative_prompt": n,
            })
        return prompts

    def generate_prompts(self):
        """生成提示词并保存，返回 prompt dict 列表"""
        prompts = self.generate_prompts_raw()
        self.save_prompts(prompts)
        return prompts

    def save_prompts(self, prompts):
        path = self.config.prompts_path
        if not path:
            raise ValueError("prompts path not configured")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)

    def load_prompts(self):
        path = self.config.prompts_path
        if not path or not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []


class ProcessManager:
    def __init__(self, config: Config):
        self.config = config

    def _default(self):
        return {
            "current_index": 0,
        }

    def load(self):
        path = self.config.process_path
        if not path or not path.exists():
            return self._default()
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return self._default()
            data = json.loads(content)
            if not isinstance(data, dict):
                return self._default()
            return data
        except (json.JSONDecodeError, IOError):
            return self._default()

    def save(self, data):
        path = self.config.process_path
        if not path:
            raise ValueError("process path not configured")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def reset(self):
        self.save(self._default())

    def update_index(self, index):
        self.save({"current_index": index})

    def can_resume(self, total):
        data = self.load()
        return 0 < data["current_index"] < total
