# sd-dynamic-helper

基于 [sd-webui-forge-neo](https://github.com/lllyasviel/stable-diffusion-webui-forge) 的动态提示词批量生图工具，支持断点续传。

## 功能

- **动态提示词生成**：使用 `dynamicprompts` 库渲染通配符/变体模板，生成提示词列表
- **批量生图**：逐条调用 WebUI API 文生图接口，每完成一张自动记录进度
- **断点续传**：中断/暂停后重新「开始生图」可从断点继续
- **种子控制**：支持固定种子、递增种子、随机种子
- **ADetailer 支持**：自动识别参数中的 ADetailer 配置，失败时自动回退重试
- **耗时统计**：单张耗时、生成总耗时、实际总耗时
- **与 WebUI 设置同步**：自动读取 sd-dynamic-prompts 插件的去重/排序设置

## 界面

| 标签页 | 说明 |
|--------|------|
| 提示词 | 显示正向/负向模板，生成/加载提示词列表 |
| 参数 | 显示生成参数详情 |
| 生图 | 种子控制、控制面板、进度条、序号显示、日志 |

### 控制按钮

| 按钮 | 说明 |
|------|------|
| 开始生图 | 新任务/续传 |
| 暂停 | 完成当前张后暂停 |
| 中断 | 立即中断当前张，保留进度可续传 |
| 取消 | 取消并清空进度 |
| 终止 | 中断并清空进度 |
| 重置进度 | 归零进度，重新开始 |

## 配置

`data/config.json`：

```json
{
  "genPara": "anima/genPara.json",
  "genPrompt": "anima/genPrompt.json",
  "process": "anima/process.json",
  "prompts": "anima/prompts.json",
  "api_url": "http://127.0.0.1:7860"
}
```

- `wildcards` 路径：`extensions/sd-dynamic-prompts/wildcards`
- WebUI 全局配置中的 `dp_wildcard_manager_no_dedupe` / `dp_wildcard_manager_no_sort` 自动同步至提示词生成

## 使用

```bash
cd sd-webui-forge-neo
venv\Scripts\activate
python extensions\sd-dynamic-helper\sd-dynamic-helper.py
```

依赖（已包含在 venv 中）：`PySide6`, `requests`, `dynamicprompts`
