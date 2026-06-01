import json
import time
from pathlib import Path

import requests

from config import Config


class WebUIClient:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.api_url.rstrip("/")
        self._adetailer_failed = False

    def is_connected(self):
        try:
            r = requests.get(f"{self.base_url}/sdapi/v1/options", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def txt2img(self, prompt, negative_prompt, gen_para, seed_mode="preset",
                seed_value=None, base_seed=0, image_index=0):
        w, h = 1024, 1024
        size_str = gen_para.get("size", "1024x1024")
        if "x" in size_str:
            parts = size_str.split("x")
            w, h = int(parts[0]), int(parts[1])

        if seed_mode == "random":
            seed = -1
        elif seed_mode == "increment":
            seed = base_seed + image_index
        elif seed_mode == "fixed":
            seed = seed_value if seed_value is not None else gen_para.get("seed", -1)
        else:
            seed = gen_para.get("seed", -1)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": gen_para.get("steps", 30),
            "cfg_scale": gen_para.get("cfg_scale", 5),
            "seed": seed,
            "width": w,
            "height": h,
            "sampler_name": gen_para.get("sampler", "DPM++ 2M SDE"),
            "batch_size": 1,
            "n_iter": 1,
            "restore_faces": False,
            "tiling": False,
            "enable_hr": False,
            "alwayson_scripts": {},
            "save_images": True,
            "do_not_save_samples": False,
        }

        schedule = gen_para.get("schedule_type", "")
        valid_schedules = [
            "automatic", "karras", "exponential", "polyexponential",
            "normal", "simple", "uniform", "sgm_uniform",
            "linear_quadratic", "kl_optimal", "ddim",
            "align_your_steps", "beta", "turbo",
            "bong_tangent", "flow_match", "flux2",
        ]
        if schedule and schedule.lower() in valid_schedules:
            payload["scheduler"] = schedule

        ad = gen_para.get("adetailer")
        has_adetailer = False
        if ad:
            ad_model = ad.get("model", "face_yolov8n.pt")
            if ad_model and ad_model != "None":
                ad_args = [
                    True,
                    {
                        "ad_model": ad_model,
                        "ad_confidence": float(ad.get("confidence", 0.3)),
                        "ad_dilate_erode": int(ad.get("dilate_erode", 4)),
                        "ad_mask_blur": int(ad.get("mask_blur", 4)),
                        "ad_denoising_strength": float(ad.get("denoising_strength", 0.4)),
                        "ad_inpaint_only_masked": bool(ad.get("inpaint_only_masked", True)),
                        "ad_inpaint_only_masked_padding": int(ad.get("inpaint_padding", 32)),
                    },
                ]
                payload["alwayson_scripts"]["ADetailer"] = {"args": ad_args}
                has_adetailer = True

        start_time = time.time()
        ad_actually_used = has_adetailer

        r = requests.post(
            f"{self.base_url}/sdapi/v1/txt2img",
            json=payload,
            timeout=600,
        )

        if r.status_code != 200 and has_adetailer:
            self._adetailer_failed = True
            del payload["alwayson_scripts"]["ADetailer"]
            r = requests.post(
                f"{self.base_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=600,
            )
        else:
            self._adetailer_failed = False

        if r.status_code != 200:
            raise RuntimeError(r.status_code, r.text)

        elapsed = time.time() - start_time

        data = r.json()
        images = data.get("images", [])
        info = data.get("info", "")
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "images": images,
            "info": info,
            "elapsed": elapsed,
            "ad_detailer_used": ad_actually_used and not self._adetailer_failed,
        }

    def interrupt(self):
        try:
            requests.post(f"{self.base_url}/sdapi/v1/interrupt", timeout=5)
        except Exception:
            pass
