关于配置config
1. 可配置 
	1. genPara，生成参数文件 
	2. genPrompt，提示词模板文件
	3. process，进度报存文件
	4. prompts，提示词保存文件
	5. api_url， webui 的 url
	6. webui, webui 路径，用于读取设置
	7. wildcards， 动态提示词使用的 wildcards 路径
2. 可以是相对路径或绝对路径
3. 相对路径基于 sd-dynamic-helper 文件夹 计算

关于配置 genpara
1. 配置 需要修改的参数，否则是默认值
2. 部分特殊处理如下
3. initArgs 中 
	1. sd_model_checkpoint 为 模型， 
	2. forge_additional_modules 为 vae 跟 text encoder, 
		1. 需要带文件后缀，且如果为空也要指定`[]`，不然如果之前有别的，不会切成空
4. ADetailer 
	1. 因为 neo 中的 ADetailer-Neo 跟 原来的参数略有不同，需要适配处理
		1. 当 ADetailer 列表 的 第一个值为 "neo"时会进行适配处理；
		2. 如果是 原版的 ADetailer 则不用加。
	2. 示例
	3. ```json
		"ADetailer": [
			"neo",
			{
			"ad_model": "face_yolov8n.pt"
			},
			{
				"ad_model": "face_yolov8n.pt"
			}
			]
		```

## 参数参考
### txt2img 相关
```py
		enable_hr=False,
        denoising_strength=0.7,
        firstphase_width=0,
        firstphase_height=0,
        hr_scale=2,
        hr_upscaler=HiResUpscaler.Latent,
        hr_second_pass_steps=0,
        hr_resize_x=0,
        hr_resize_y=0,
        hr_checkpoint_name=None,
        hr_sampler_name=None,
        hr_scheduler=None,
        hr_prompt="",
        hr_negative_prompt="",
        prompt="",
        styles=[],
        seed=-1,
        subseed=-1,
        subseed_strength=0.0,
        seed_resize_from_h=0,
        seed_resize_from_w=0,
        sampler_name=None,  # use this instead of sampler_index
        scheduler=None,
        batch_size=1,
        n_iter=1,
        steps=None,
        cfg_scale=7.0,
        width=512,
        height=512,
        restore_faces=False,
        tiling=False,
        do_not_save_samples=False,
        do_not_save_grid=False,
        negative_prompt="",
        eta=1.0,
        s_churn=0,
        s_tmax=0,
        s_tmin=0,
        s_noise=1,
        override_settings={},
        override_settings_restore_afterwards=True,
        script_args=None,  # List of arguments for the script "script_name"
        script_name=None,
        send_images=True,
        save_images=False,
        alwayson_scripts={},
        controlnet_units: List[ControlNetUnit] = [],
        adetailer: List[ADetailer] = [],
        animatediff: AnimateDiff = None,
        roop: Roop = None,
        reactor: ReActor = None,
        sag: Sag = None,
        sampler_index=None,  # deprecated: use sampler_name
        use_deprecated_controlnet=False,
        use_async=False,
```


### ADetailer 相关
```py
		ad_model: str = "None",
		ad_model_classes: str = "",
		ad_tab_enable: bool = True,
		ad_prompt: str = "",
		ad_negative_prompt: str = "",
		ad_confidence: float = 0.3,
		ad_mask_k_largest: float = 0.0,
		ad_mask_min_ratio: float = 0.0,
		ad_mask_max_ratio: float = 1.0,
		ad_dilate_erode: int = 4,
		ad_x_offset: int = 0,
		ad_y_offset: int = 0,
		ad_mask_merge_invert: Literal["None", "Merge", "Merge and Invert"] = "None",
		ad_mask_blur: int = 4,
		ad_denoising_strength: int = 0.4,
		ad_inpaint_only_masked: bool = True,
		ad_inpaint_only_masked_padding: int = 32,
		ad_use_inpaint_width_height: bool = False,
		ad_inpaint_width: int = 512,
		ad_inpaint_height: int = 512,
		ad_use_steps: bool = False,
		ad_steps: int = 28,
		ad_use_cfg_scale: bool = False,
		ad_cfg_scale: float = 7.0,
		ad_use_checkpoint: bool = False,
		ad_checkpoint: str = None,
		ad_use_vae: bool = False,
		ad_vae: str = None,
		ad_use_sampler: bool = False,
		ad_sampler: str = "DPM++ 2M Karras",
		ad_scheduler: str = "Use same scheduler",
		ad_use_noise_multiplier: bool = False,
		ad_noise_multiplier=1.0,
		ad_use_clip_skip: bool = False,
		ad_clip_skip: int= 1,
		ad_restore_face: bool = False,
		ad_controlnet_model: str = "None",
		ad_controlnet_module: str = "None",
		ad_controlnet_weight: float = 1.0,
		ad_controlnet_guidance_start: float = 0.0,
		ad_controlnet_guidance_end: float = 1.0,
```
