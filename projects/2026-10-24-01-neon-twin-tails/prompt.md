# 2026-10-24 · NEON 双马尾 · 提示词（原样记录）

## 初始任务

```text
**目标**
基于提供的参考素材，制作一段 23 秒的“双马尾”3D卡通娃娃跳舞视频
**输入素材**
- **风格基准 (视频 A - 23秒卡通版)**：提供目标3D娃娃的美术风格、材质渲染及镜头剪辑节奏（原为披肩发）。视频 A 位于 D:\Downloads_D\科普视频学习与制作\，是包含 Comment [neon] 的 mp4 文件
- **动作源 (视频 B - 完整真人MV)**：提供原始的舞蹈动作与运镜参考。视频 B 同样位于 D:\Downloads_D\科普视频学习与制作\，名称是 A2O LITE 'NEON' Official Video.mkv

**核心要求**
1. **角色特征**：复刻视频 A 的3D卡通娃娃画风与服装，但将发型修改为**双马尾**。
2. **规格对齐**：成片时长严格控制在 23 秒，动作与节奏需与视频 A 对应的真人片段保持同步。
```

## 后续交互

这一次交互很多，主要卡在“用什么生成”上，制作本身反而顺利。下面按顺序列出，用户的话照原文记录。公开仓库里不写邮箱地址，所以两个账号的邮箱换成了 `[工作账号]`、`[个人账号]`。

| # | 情况 | 用户 |
|---|---|---|
| 1 | Claude 查过本机和可用的服务：没有 NVIDIA 显卡，Sora API 已停用，OpenAI 余额为零，Weave 还没关联。给出三个选项：关联 Weave、用户自己生成、换别的 API key | 选「Link Weave (Recommended)」 |
| 2 | 中途应用被关闭 | The app was quit while you were working. Please continue from where you left off. |
| 3 | Weave 仍然提示没关联；Claude 准备好了片段、提示词和成片脚本 | I've linked my Figma account to Weave. Find the video-edit models, quote the cost, and continue. |
| 4 | Claude 查到 Figma 连接器登录的是 `[工作账号]`，和关联到 Weave 的不是同一个账号 | `[工作账号]` 登录的 figma 账号已经作废了，我智能关联 `[个人账号]` 的 figma 账号，你觉得现在该怎么办？switch connector 吗？ |
| 5 | Claude 建议在 claude.ai 的 Connectors 里把 Figma 连接器换成个人账号 | 好了，确认登录并关联的是 `[个人账号]` 的账号，额度只有 150 credits |
| 6 | 150 credits 不够分三段跑，Claude 把三段拼成一段 19 秒的视频。上传工具返回的是令牌，用 curl 上传被权限检查拦下 | I approve: upload the combined clip to the Weave upload endpoint with curl using the token the upload tool returned, then get the quote. |
| 7 | 上传成功，但 Weave 免费版不能用视频模型 | I'll upgrade Weave to a paid plan. When I say it's done, quote Kling 4.0 Video Edit on the uploaded clip and wait for my approval. |
| 8 | （附 Weave 套餐页截图） | 关于升级套餐，你有何建议 |
| 9 | Claude 建议按月订 Starter，先跑最难的双人舞当测试 | （附 Starter、1,500 credits 截图）升级到 Starter 了，请你继续 |
| 10 | clip2 测试报价：1080p 216 / 720p 144 | 选「Approve 720p」 |
| 11 | 测试结果：棕发娃娃 4.3 秒后才变成双马尾；用参考图重跑报价 144 | 选「Approve 144 credits」 |
| 12 | clip1 80 + clip3 96 | 选「Approve both (176)」 |
| 13 | clip1 开场镜头还是长发、字样残影、取景偏松；只重做开场镜头 48 | 选「Approve 48 credits」 |
| 14 | 预览 v2：开场特写比原片紧，问保留还是再重跑一次 | Keep v2 as the final cut. Archive it in the repo as a new project like the earlier NEON ones. |

## 提示词拆解

| 要素 | 写法 | 效果 |
|---|---|---|
| 结构 | 目标 / 输入素材 / 核心要求，要求编号 | ✅ 可以逐条验收：双马尾、画风服装、23 秒、和真人片段同步 |
| 输入 | 用路径和文件名关键词指认 | ✅ 一次就找到了 |
| 素材分工 | A 管画风和剪辑节奏，B 管动作和运镜 | ⚠️ 字面上像是要“用 B 的动作重新生成”。但 A 本身就是 B 开头的重绘，两者已经同步，所以改成直接编辑 A：时间轴不动，同步自然保住。值得在提示词里写明“允许直接在 A 上改” |
| 规格 | “严格 23 秒”“与对应的真人片段同步” | ✅ 可以量化验收：690 帧；音频偏差 5 ms；画面在 ±1 帧以内 |
| 未写明 | 用什么生成服务、预算、分辨率 | ⚠️ 前半程都花在这些上：Sora API 已停用、Weave 账号对不上、免费版不能用视频模型、升级套餐。每次运行都要单独确认费用 |
| 未写明 | 原片里的字样和签名要不要保留；取景要多严格 | ⚠️ Kling 会抹掉文字，取景也会偏；这次按原片补回了字样和签名，取景偏差最后接受了 |

## 复用版（建议）

```text
任务：把 <视频 A> 里的 <角色> 的 <属性，比如发型> 改成 <目标>，其余（画风、服装、动作、镜头、剪辑、时长）都照原片。
可以直接在 A 上做视频编辑（A 已经和 <参考视频 B> 同步，以 B 的音轨为准）。
生成：用 <服务 / 模型>，账号 <…>，预算不超过 <N> credits，分辨率 <720p / 1080p>；每次运行前先报价。
保留：原片的 <字样 / 签名 / Logo>（被抹掉的话按原片补回）；取景要和原片一致，尤其是 <某个镜头>。
验收：时长 <N> 秒（<帧数> 帧）；画面和原片逐帧对齐（±1 帧）；音轨用 <…>，−14 LUFS。
输出：1920×1080，30 fps，H.264 + AAC，文件名 <…>。
```
