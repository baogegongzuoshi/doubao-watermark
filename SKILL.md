---
name: doubao-watermark
description: 豆包水印/豆包解析一体包。触发条件：消息中出现豆包分享链接样式（doubao.com/thread/...、dola.com/thread/... 等含 /thread/ 的豆包链接），或提到"豆包""无印豆包""无水印""豆包解析""豆包图片""豆包视频""下载豆包"等关键词时使用。普通下载走 doubao_engine.py（先报数确认、时间过滤、按生成时间从旧到新排序、H.264 mp4）；要求跳过失败品/质量筛选走 doubao_smart.py（大模型审读，按对话反馈极性分层）。
---

# 豆包水印（豆包解析）一体包

**触发条件（满足其一即加载本 skill）：**
1. 消息里出现豆包分享链接样式：`doubao.com/thread/xxx`、`dola.com/thread/xxx`（含 /thread/ 的豆包链接）
2. 提到"豆包"、"无印豆包"、"无水印"、"豆包解析"、"下载豆包图片/视频"等

一个包、两种模式、共享同一份解析引擎（`scripts/`，纯 Python 标准库，无需装依赖）：

- **普通模式（默认）** `scripts/doubao_engine.py` —— 线上解析的工具化：scan 报数 → 用户确认 → 下载
- **智能过滤模式** `scripts/doubao_smart.py` —— 用户要求"跳过生成失败的/帮我筛质量"时：下载缩略图样本 → 大模型三层审读 → verdicts 分层 → 只下成功品

Python 路径：`C:/Users/Admin/.workbuddy/binaries/python/versions/3.13.12/python.exe`

## 模式路由

| 用户诉求 | 用法 |
|---|---|
| 发来 /thread/ 链接要下载（默认） | 普通模式 |
| 提示词只说"要图"/"要视频" | 普通模式 + `--type image/video`；没说则默认都提 |
| "只要今天的 / 最近几小时的" | 普通模式 + `--today` / `--hours N` / `--since "2026-09-17 08:00"` |
| "跳过失败品 / 筛一下质量 / 失败的不要" | 智能过滤模式 |
| 没说清要不要过滤 | 先用普通模式 scan 报数，再问用户 |
| 只问原理/格式 | 直接回答（见文末原理速查） |

## 普通模式命令

```
# 1. 报数（不下载）：输出图片/视频数量、时间、提示词，清单按生成时间从旧到新
... scripts/doubao_engine.py scan "<share_url>" [--json-out FILE]

# 2. 确认后下载：文件名带时间戳序号（近的在前）
... scripts/doubao_engine.py download "<share_url>" --out <目录> \
    [--type all|image|video] [--today | --hours N | --since "..." [--until "..."]] \
    [--ids id1,id2] [--limit N] [--best]

# 3. 视频无损规整 mp4（ffmpeg -c copy）；--transcode 转 H.264（有损，兼容性兜底）
... scripts/doubao_engine.py mp4 <文件...> [--transcode]

# 4. 本地网页展示（jiagev 风格）：图片/视频双选项卡 + 单个下载 + 一键批量 ZIP + 手机逐个保存
... scripts/doubao_web.py [端口]     # 默认 8765，浏览器开 http://127.0.0.1:8765，粘贴 /thread/ 链接点解析
```

## 智能过滤模式命令

```
# 1. 拉待审样本（图片用缩略图、视频用封面，流量小）+ manifest.json（含 prompt/context/时间/msg_index）
... scripts/doubao_smart.py candidates "<share_url>" --review <目录>

# 2.（大模型亲自审读，规则见下）写 <目录>/verdicts.json

# 3. 按判定下载（--dry-run 先预览；--tier core 只下核心）
... scripts/doubao_smart.py download "<share_url>" --out <目录> --verdicts <目录>/verdicts.json [--type all] [--dry-run]
```

### 审读规则（大模型执行，三层判断，按优先级）

1. **对话级反馈极性（最重要）**：通读全部 context，梳理用户对每批结果的反馈：
   - 用户**明确认可**（如"可以"）的批次 → `core`
   - 用户**批评过并要求改造**的图、以及**响应批评的迭代产物**（若用户未认可）→ `skip`
   - 用户**未提意见**的图 → `ok`
   - 不是"越新越好"！最后批次不一定都好；没有反馈信号时才用时间/迭代关系辅助推断
2. **视觉层**：人物/手部/面部明显畸形、文字乱码、大面积空白色块、明显贴图感/拼接违和、糊成一团
3. **单图提示词比对（仅辅助）**：与该图自己的 prompt 严重不符才扣分；轻微偏差不算失败，以对话最新意图为准
4. **数据层硬失败（不看图直接 skip）**：视频 status≠3 或 model_status≠10、tips 非空、duration=0、无有效 URL

verdicts.json 格式：
```json
{"verdicts": [{"id": "创作id", "tier": "core|ok|skip", "verdict": "keep|skip", "reason": "简短理由"}]}
```

## 铁律

- 链接必须含 `/thread/`，否则提示用户在豆包里重新"分享-复制链接"
- **先报数再下载**：任何下载前必须报告"共 N 图 M 视频"并获用户确认
- 直链带签名有时效：scan 后当次下载，过期重跑即可
- 视频默认 H.264 变体（通用兼容）；仅用户要最高清才 `--best`（可能 H.265，部分播放器不支持）
- 两种模式结果都按生成时间**从旧到新**排序命名（早生成的序号在前）
- 引擎遇"页面未返回可解析数据"会明确报错（风控/网络抖动），重试即可，不要静默当 0 处理
- 仅供学习交流，内容版权归豆包用户所有

## 原理速查（用户问起时用）

- 页面内嵌 fn-args JSON 存在**多层嵌套 JSON 字符串**，需递归解析；创作在 `creation_block.creations`：`type=1` 图（`image.image_ori_raw`）、`type=2` 视频（`video.video_model` 含 fallback_api）
- 无水印：fallback_api 改参数 `logo_type=unwatermarked&codec_type=8` 请求 → `video_list[].main_url`（qAAB 形态 = AES-128-CBC，key 由 `key_seed` 经 sha512(sha512(seed[:32])+SALT) 派生）解密，**明文尾部 PKCS7 填充需去除**
- 720p=H.264（通用）、1080p=bytevc1/H.265（兼容性差）——这就是"下载格式不常见"的根源
- 线上 jiagev.com（doubao-nomark 部署）：`/parse-video` 可用，`/parse` 图片模块对新页面结构已失效（返回 0 张）——所以本地引擎是主通道
