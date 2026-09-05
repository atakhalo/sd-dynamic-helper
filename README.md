# sd-dynamic-helper

webui 动态提示词批量生图工具，支持断点续传。

## 核心功能
- **动态提示词生成**：使用 `dynamicprompts` 库渲染通配符/变体模板，生成提示词列表
- **批量生图**：逐条调用 WebUI API 进行 文生图
- **断点续传**：中断/暂停后重新「开始生图」可从断点继续

## 安装使用
安装 （打包版跳过）
1. git clone 到 webui extensions 目录
2. 运行 pipInNeoExtensions.bat 安装 PySide6、webuiapi、dynamicprompts 到虚拟环境
	1. ```bat
		cd /d "%~dp0..\.."
		call venv\Scripts\activate
		uv pip install PySide6 webuiapi dynamicprompts
		```
使用
1. 以 api 形式运行 webui，
	1. 即在 webui-user.bat 中添加`--api`参数
	2. 如 `set COMMANDLINE_ARGS=--uv --theme dark --api`
2. 编辑 genPrompt(提示词模板)、genPara（生成参数）
3. 运行 runInNeoExtensions.bat （打包版运行 sd-dynamic-helper.exe）
	1. ```bat
		cd /d "%~dp0..\.."
		venv\Scripts\python.exe extensions\sd-dynamic-helper\scripts\sd-dynamic-helper.py
		```
4. 程序会自动读取 data/config.json
	1. 显示 提示词、参数 供确认
	2. 点 生成提示词 根据 模板生成生图提示词
	3. 点 开始生图 后可开始生图
		1. 生图文件保存在 webui 默认路径
	4. 可暂停、中断，关闭程序后下次运行会读取进度

其他

也可以安装到其他目录，安装使用 pipInOther.bat 运行使用 runInOther.bat
## 其他功能
**生图控制**
| 按钮     | 说明                           |
| -------- | ------------------------------ |
| 开始生图 | 新任务/续传                    |
| 暂停     | 完成当前张后暂停               |
| 中断     | 立即中断当前张，保留进度可续传 |
| 跳过     | 中断当前张、推进进度后暂停     |
| 取消     | 完成当前张后清空进度           |
| 终止     | 中断并清空进度                 |
| 重置进度 | 归零进度，重新开始             |

- **种子控制**：支持编辑种子（可随机），生图时种子模式可选（固定、递增）
- **耗时统计**：单张耗时、生成总耗时

## 关于配置
关于配置config
1. 可配置 
	1. genPara — 生成参数文件
	2. genPrompt — 提示词模板文件
	3. process — 进度保存文件
	4. prompts — 提示词保存文件
	5. api_url — WebUI 的 URL
	6. webui — webui 路径，用于读取设置
	7. wildcards — 动态提示词使用的 wildcards 路径
	8. fix_pnginfo — 生图后把图片元数据中的 `Template` / `Negative Template` 改为 genPrompt.json 中的模板内容（默认 true；设为 false 关闭）
2. 可以是相对路径或绝对路径
3. 普通相对路径基于 sd-dynamic-helper 文件夹 计算
4. `$$` 前缀：以 **config.json 所在目录** 为基准计算相对路径（便于子目录配置引用外部文件）
	1. `"$$/genPrompt.json"` — 与 config.json 同目录
	2. `"$$../genPara.json"` — config.json 所在目录的上一级
	3. 示例：`data/animaV11/2-animaV11-Pre/config.json` 中
		- `"genPrompt": "$$/genPrompt.json"`（等价原 `data/animaV11/2-animaV11-Pre/genPrompt.json`）
		- `"genPara": "$$../genPara.json"`（等价原 `data/animaV11/genPara.json`）

关于图片元数据模板信息
1. 生图结束后，程序在 WebUI 输出目录（`output/txt2img-images`，含按日期保存的子目录）中查找最近的图片，并把其元数据（PNG 的 tEXt `parameters`；JPG/WebP 等图片的 EXIF `UserComment`）中 `Template` 与 `Negative Template` 的内容替换为 genPrompt.json 中 `prompt` / `negative_prompt`（初始模板）
2. 查找与校验策略：以生成结束时刻为中心 ±10 秒窗口内按修改时间新→旧依次候选 → 校验元数据中 `Prompt` 与 `Seed` 和本次生图一致（防止误改其他图片）→ 一致才执行修改
3. 若图片元数据中没有这两个字段，会自动补写
4. 元数据中的其他字段（Prompt、Seed、参数等）保持不变

关于配置 genpara
1. 配置 需要修改的参数，否则是默认值； 参数可参考 [data/args.md](data/args.md)
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


## 其他
仅在webui forgeneo 测试，理论上兼容原版webui

依赖：`PySide6`, `webuiapi`, `dynamicprompts`

