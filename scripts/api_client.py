import time
from pathlib import Path
from urllib.parse import urlparse

import webuiapi

from scripts.config import Config


# ADetailer-Neo 的 ADetailerArgs pydantic 模型使用 extra="forbid"，
# webuiapi.ADetailer.to_dict() 输出的部分字段未被该模型定义，
# 会导致 ValidationError。以下是该模型支持的字段白名单。
_ADETAILER_ARGS_COMPAT_FIELDS = {
    "ad_model",
    "ad_model_classes",
    "ad_tab_enable",
    "ad_prompt",
    "ad_negative_prompt",
    "ad_confidence",
    "ad_mask_filter_method",
    "ad_mask_k",
    "ad_mask_min_ratio",
    "ad_mask_max_ratio",
    "ad_dilate_erode",
    "ad_x_offset",
    "ad_y_offset",
    "ad_mask_merge_invert",
    "ad_mask_blur",
    "ad_denoising_strength",
    "ad_inpaint_only_masked",
    "ad_inpaint_only_masked_padding",
    "ad_use_inpaint_width_height",
    "ad_inpaint_width",
    "ad_inpaint_height",
    "ad_use_steps",
    "ad_steps",
    "ad_use_cfg_scale",
    "ad_cfg_scale",
    "ad_use_checkpoint",
    "ad_checkpoint",
    "ad_use_vae",
    "ad_vae",
    "ad_use_sampler",
    "ad_sampler",
    "ad_scheduler",
    "ad_use_noise_multiplier",
    "ad_noise_multiplier",
    "ad_restore_face",
    "ad_controlnet_model",
    "ad_controlnet_module",
    "ad_controlnet_weight",
    "ad_controlnet_guidance_start_end",
}


def _sanitize_adetailer_dict(raw: dict) -> dict:
    # Filter webuiapi.ADetailer.to_dict() output to only include fields
    # supported by ADetailer-Neo's ADetailerArgs pydantic model, with conversions.
    d = {}
    # 复制白名单内的字段
    for k in _ADETAILER_ARGS_COMPAT_FIELDS:
        if k in raw:
            d[k] = raw[k]
    # 合并 controlnet guidance start/end → tuple
    gs = raw.get("ad_controlnet_guidance_start")
    ge = raw.get("ad_controlnet_guidance_end")
    if gs is not None or ge is not None:
        d["ad_controlnet_guidance_start_end"] = (gs if gs is not None else 0.0,
                                                   ge if ge is not None else 1.0)
    # 转换 ad_mask_k_largest → ad_mask_k
    if "ad_mask_k_largest" in raw and "ad_mask_k" not in d:
        d["ad_mask_k"] = int(raw["ad_mask_k_largest"])
    # 确保必要字段
    if "ad_model" not in d:
        d["ad_model"] = raw.get("ad_model", "None")
    return d


class WebUIClient:
    def __init__(self, config: Config):
        self.config = config
        # 解析 URL 获取 host 和 port
        parsed = urlparse(config.api_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 7860
        self.base_url = config.api_url.rstrip("/")
        # 创建 webuiapi 客户端
        self.api = webuiapi.WebUIApi(
            host=self.host,
            port=self.port,
            use_https=parsed.scheme == "https",
        )

    def is_connected(self):
        try:
            self.api.get_samplers()
            return True
        except Exception:
            return False

    def _ensure_model_with_modules(self, initArgs: dict | None):
        """Forge 的 forge_additional_modules 无法通过 initArgs 动态生效，
        需要先通过 options API 设置全局选项并触发模型重载。"""
        if not initArgs:
            return
        modules = initArgs.get("forge_additional_modules")
        checkpoint = initArgs.get("sd_model_checkpoint")
        if not modules and not checkpoint:
            return
        # 先设置附加模块，再切换模型（顺序重要：模块需在模型加载前就绪）
        options = {}
        if modules is not None:
            options["forge_additional_modules"] = modules
        if checkpoint:
            options["sd_model_checkpoint"] = checkpoint
        self.api.set_options(options)

    def txt2img(self, prompt, negative_prompt, gen_para, seed_mode="preset",
                seed_value=None, base_seed=0, image_index=0):
        # ---- 模型/模块预处理 ----
        # forge_additional_modules 必须通过全局 options API 设置才能生效
        initArgs = gen_para.get("initArgs")
        if initArgs:
            self._ensure_model_with_modules(initArgs)

        # ---- 种子处理 ----
        if seed_mode == "random":
            seed = -1
        elif seed_mode == "increment":
            seed = base_seed + image_index
        elif seed_mode == "fixed":
            seed = seed_value if seed_value is not None else gen_para.get("seed", -1)
        else:
            seed = gen_para.get("seed", -1)

        # ---- ADetailer ----
        adetailer_list = []
        ads = gen_para.get("ADetailer")
        if ads:
            # 兼容处理：如果 ADetailer 列表的第一个值是版本标识 "neo"，
            # 跳过该标识，从第二个元素开始作为实际的 ADetailer 配置项处理
            if ads and isinstance(ads[0], str) and ads[0] == "neo":
                ad_configs = ads[1:]
            else:
                ad_configs = ads
            for ad in ad_configs:
                model = ad.get("ad_model", "")
                if not model or model == "None":
                    continue
                # 使用 webuiapi.ADetailer 建立对象，再覆写 to_dict 以输出
                # 与 ADetailer-Neo pydantic 模型兼容的字段
                ad_obj = webuiapi.ADetailer(**ad)
                _orig_to_dict = ad_obj.to_dict
                ad_obj.to_dict = lambda _orig=_orig_to_dict: _sanitize_adetailer_dict(_orig())
                adetailer_list.append(ad_obj)

        # ---- 其余参数直接从 gen_para 解包传给 webuiapi ----
        # 排除已被特殊处理的键
        SPECIAL_KEYS = {"initArgs", "seed", "ADetailer", "adetailer", "save_images"}
        api_kwargs = {k: v for k, v in gen_para.items() if k not in SPECIAL_KEYS}

        start_time = time.time()

        result = self.api.txt2img(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            save_images=True,
            adetailer=adetailer_list if adetailer_list else None,
            **api_kwargs,
        )

        elapsed = time.time() - start_time

        # webuiapi 返回的 result.info 已经是 dict
        info = result.info if isinstance(result.info, dict) else {}

        return {
            "images": result.images,  # list of PIL Images
            "info": info,
            "elapsed": elapsed,
        }

    def get_options(self) -> dict:
        """获取 WebUI 当前全局设置。"""
        return self.api.get_options()

    def dump_options_to_file(self, filepath: str | Path) -> str:
        """将 WebUI 当前全局设置导出为 JSON 文件。返回文件路径。"""
        import json
        options = self.get_options()
        target = Path(filepath).resolve()
        with open(target, "w", encoding="utf-8") as f:
            json.dump(options, f, ensure_ascii=False, indent=2)
        return str(target)

    def interrupt(self):
        try:
            self.api.interrupt()
        except Exception:
            pass
