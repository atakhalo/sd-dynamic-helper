import json
from pathlib import Path

from dynamicprompts.generators import CombinatorialPromptGenerator
from dynamicprompts.wildcards import WildcardManager

from config import Config


class PromptManager:
    def __init__(self, config: Config):
        self.config = config
        self.wildcard_manager = WildcardManager(
            path=str(config.wildcards_path)
        )
        self.generator = CombinatorialPromptGenerator(
            wildcard_manager=self.wildcard_manager
        )

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

    def generate_prompts(self):
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
                "index": i,
                "prompt": p,
                "negative_prompt": n,
            })

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
    IDLE = "idle"
    GENERATING = "generating"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    def __init__(self, config: Config):
        self.config = config

    def _default(self):
        return {
            "current_index": 0,
            "total_count": 0,
            "status": self.IDLE,
            "results": [],
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

    def update_index(self, index, total, status=None, result=None):
        data = self.load()
        data["current_index"] = index
        data["total_count"] = total
        if status:
            data["status"] = status
        if result is not None:
            data["results"].append(result)
        self.save(data)
        return data

    def can_resume(self):
        data = self.load()
        return (
            data["status"] in (self.PAUSED, self.GENERATING)
            and data["current_index"] < data["total_count"]
        )

    def get_resume_index(self):
        data = self.load()
        if self.can_resume():
            return data["current_index"]
        return 0
