# doubao-watermark

豆包（Doubao）分享链接图片 / 视频无水印解析与下载工具，打包为 [WorkBuddy](https://www.workbuddy.cn) Skill。

## 特性

- **无水印下载**：图片直链 + 视频走 `fallback_api` 改参（`logo_type=unwatermarked`）+ AES 解码 `main_url`，实测可下 H.264 720p 无水印 mp4
- **先报数再下载**：`scan` 输出图片/视频数量、时间、提示词清单，确认后才下载
- **时间过滤**：`--today` / `--hours N` / `--since`，只下今天或最近几小时的内容
- **时间排序**：清单与文件名均按时间**从近到远**排列
- **智能过滤模式（可选）**：下载缩略图样本 → 大模型三层审读（对话级反馈极性 / 视觉缺陷 / 语义比对）→ 只下载通过筛选的作品，自动跳过生成失败品
- **零依赖**：纯 Python 标准库实现（含纯 Python AES-128-CBC），无需安装第三方包

## 用法

```bash
# 报数（不下载）
python scripts/doubao_engine.py scan "<doubao.com/thread/xxx 链接>"

# 确认后下载
python scripts/doubao_engine.py download "<链接>" --out ./output --type all

# 智能过滤（先取样本审读，再按 verdicts 下载）
python scripts/doubao_smart.py candidates "<链接>" --review ./review
python scripts/doubao_smart.py download "<链接>" --out ./output --verdicts ./review/verdicts.json
```

完整参数与工作流说明见 [SKILL.md](SKILL.md)。

## 目录结构

```
doubao-watermark/
├── SKILL.md                  # WorkBuddy skill 入口（触发条件 + 模式路由 + 审读规则）
├── scripts/
│   ├── doubao_engine.py      # 解析引擎：scan / download / mp4（无损规整）
│   └── doubao_smart.py       # 智能过滤：candidates / download（分层 verdicts）
└── README.md
```

## 致谢

- [ihmily/doubao-nomark](https://github.com/ihmily/doubao-nomark) —— 本项目的视频无水印思路（fallback_api 改参 + key_seed 解码）参考自该项目的 `doubao_parser` 实现
- 本项目针对豆包页面结构变化做了适配：图片解析不再依赖固定字段路径，采用「泛走查 + 多级兜底」提取（线上解析站的图片接口对新结构已失效，本项目实测仍可完整解析）

## 免责声明

本项目仅供学习交流使用，所解析内容的版权归原作者所有。请勿用于商业用途或侵犯他人权益。
