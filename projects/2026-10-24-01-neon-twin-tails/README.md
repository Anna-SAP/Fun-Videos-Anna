# 2026-10-24 · NEON 双马尾：给 AI 卡通版娃娃换发型

| 项 | 内容 |
|---|---|
| 日期 | 2026-10-24 |
| 类型 | AI 视频编辑（只改发型，动作、镜头和节奏不变） |
| 工具 | Kling 4.0 Video Edit（经 Figma Weave，Starter 套餐）+ Claude Code（本机）+ ffmpeg、numpy/scipy、Pillow |
| 输入 | 卡通版片段（视频 A）、官方 MV（视频 B），都是第三方素材，不入库 |
| 产出 | 1 条成片 + 5 段 Kling 生成素材 |
| 对话 | Claude 桌面版 Code 会话，接着 [NEON](../2026-10-21-01-neon-cartoon-vs-mv-split/) 和 [NEON ×3](../2026-10-22-01-neon-three-universes/) 做 |

## 成片

| 预览 | 文件 | 时长 | 规格 | 大小 |
|---|---|---|---|---|
| <img src="thumbs/neon_twin-tails_poster.jpg" width="160"> | [`media/neon_twin-tails.mp4`](media/neon_twin-tails.mp4)<br>原名：NEON_双马尾_23s.mp4 | 0:23.0 | 1920×1080 · 30 fps · H.264 CRF 18 · AAC 256 kbps · −14 LUFS | 16.0 MB |

逐帧预览：[成片](thumbs/neon_twin-tails_sheet.jpg) · [原版 vs 双马尾](thumbs/neon_twin-tails_vs-original.jpg)（上排视频 A，下排成片，同一时刻）

**一句话：** 视频 A 里的 3D 娃娃从第一帧起都换成高位双马尾，配白色毛绒发圈，各自保留黑发、栗棕发；画风、服装、动作、镜头和时长都照原片，配 MV 原声，和真人 MV 同步。

| 时间（成片） | 视频 A 帧 | 画面 | 来源 |
|---|---|---|---|
| 0:00–0:02.7 | 0–81 | 单人娃娃，镜头推到双人特写；「A2O LITE」字样闪入 | Kling 重做的开场镜头（shot1），字样和签名按原片补回 |
| 0:02.7–0:04.6 | 82–137 | 浅色背景双人、侧脸 + 手特写 | Kling clip1 |
| 0:04.6–0:07.3 | 138–218 | 手部特写，没有头发 | 视频 A 原片 |
| 0:07.3–0:15.8 | 219–474 | 3 帧双人闪切，然后双人舞（远景推到中景） | Kling clip2 第 2 次 |
| 0:15.8–0:17.6 | 475–526 | A2O / 「Stage 1」图形，没有娃娃 | 视频 A 原片 |
| 0:17.6–0:23.0 | 527–689 | 双人近景舞，拉开成群舞队形 | Kling clip3 |

## 自有素材（Kling 生成，Git LFS）

`assemble_twin_tails.py` 直接读这个文件夹（`materials/kling/`）。重新生成要花 credits，所以都存了下来，包括没用上的那一次。

| 文件 | 内容 | 状态 | 时长 | 大小 | Credits |
|---|---|---|---|---|---|
| [`kling/shot1_kling4_720p_run1.mp4`](materials/kling/shot1_kling4_720p_run1.mp4) | 开场镜头重做：参考图 + 要求去掉字样 | 用于 0–81 帧 | 3.04 s | 1.7 MB | 48 |
| [`kling/clip1_kling4_720p_run1.mp4`](materials/kling/clip1_kling4_720p_run1.mp4) | 开场 4.6 秒，带参考图 | 只用 82–137 帧，前 2.7 秒被 shot1 取代 | 5.04 s | 2.9 MB | 80 |
| [`kling/clip2_kling4_720p_run1.mp4`](materials/kling/clip2_kling4_720p_run1.mp4) | 双人舞，没给参考图 | 未用：棕发娃娃到 4.3 秒才变成双马尾 | 9.04 s | 5.5 MB | 144 |
| [`kling/clip2_kling4_720p_run2.mp4`](materials/kling/clip2_kling4_720p_run2.mp4) | 双人舞，带参考图 | 用于 219–474 帧 | 9.04 s | 5.9 MB | 144 |
| [`kling/clip3_kling4_720p_run1.mp4`](materials/kling/clip3_kling4_720p_run1.mp4) | 结尾群舞，带参考图 | 用于 527–689 帧 | 6.04 s | 5.2 MB | 96 |
| [`reference/ref_twintails_clip2run1_5.17s.jpg`](materials/reference/ref_twintails_clip2run1_5.17s.jpg) | 参考图：clip2 第 1 次 5.17 秒处，两个娃娃都已经是双马尾 | 作为 `@Image1` 用于后四次 | — | 52 KB | — |

全部是 Kling 输出的原样：1280×720、24 fps，带一条没用到的音轨。五次一共 **512 credits**（Starter 套餐每月 1,500）。

## 第三方素材（不入库，只登记）

| 素材 | 说明 | 本地文件 / 体积 |
|---|---|---|
| 视频 A：卡通版片段 | Higgsfield 创作者用 AI 重绘的 A2O LITE《NEON》开头，1276×718、30 fps、23.06 秒（同 [NEON](../2026-10-21-01-neon-cartoon-vs-mv-split/)）。左上角有作者签名 | `🩵 Comment [neon] 🩵 … Made @higgsfield.ai.mp4` / 3.1 MB |
| 视频 B：官方 MV | A2O LITE《NEON》Official Video，只用了它的音轨 | `A2O LITE 'NEON' Official Video.mkv` / 201 MB |

成片的每一帧都来自视频 A，要么是原片，要么是 Kling 在原片上改了发型。

## 提示词

见 [prompt.md](prompt.md)，是原样记录的。中间换账号、升级套餐、每次运行确认费用的交互也都记在里面。

## 关键制作步骤

1. **先找能用的生成通道。** 本机只有 Intel Arc 核显，跑不了视频模型。
   - OpenAI 的 Sora 2 / Videos API 已于 2026-09-24 停用，图像接口返回余额为零。
   - Figma Weave 认的是 Claude 里 Figma 连接器登录的那个账号。连接器登录的是已经作废的工作账号，需要先在 claude.ai 的 Connectors 里换成个人账号。
   - Weave 免费版（150 credits）不能用任何视频模型，升级到 Starter（$24/月，1,500 credits）。
   - 选了 **Kling 4.0 Video Edit**：输入 3–30 秒、短边至少 700 px，720p 每秒 16 credits，1080p 每秒 24 credits。Weave 上同类模型的标价：Runway Aleph 约 90 credits / 次，Kling o1 Edit 约 147，Runway Aleph 2 约 504。
2. **编辑视频 A，不从 MV 重新生成动作。**
   - 视频 A 本身就和 MV 同步：用 [`find_offset.py`](../../tools/av/find_offset.py) 复核，`MV 时间 = 视频 A 时间 − 0.0407 s`，15 个窗口里 12 个一致，没有漂移；另外 3 个是旋律重复造成的假峰（[NEON ×3](../2026-10-22-01-neon-three-universes/) 也遇到过）。
   - 视频编辑不改时间轴，所以只要每一帧还落在原来的位置上，和真人 MV 的同步就自然保住了。如果用 MV 驱动动作迁移，镜头、剪辑节奏和同步都得重做。
3. **只送有头发的镜头。** 先逐帧找出视频 A 的切点（见上表），手部特写（2.7 秒）和图形段（1.7 秒）直接用原片。上传的片段按帧精确剪出，缩放到 1280×720，最后一帧补到整秒：Kling 按整秒计费和输出，输入长度和请求时长一致时，时间轴不会被拉伸。脚本见 [`scripts/prepare_uploads.sh`](scripts/prepare_uploads.sh)。
4. **先拿最难的一段测试。** 双人舞 clip2 甩头发最多，先只跑它（720p，144 credits）。
   - 双马尾的样子很好，但 Kling **只在甩头发的瞬间改发型**：黑发娃娃 1.3 秒才变，棕发娃娃 4.3 秒才变，之前都是长发。
   - 修正方法：用这一版里两个娃娃都已经变好的一帧（5.17 秒）当参考图 `@Image1`，提示词写明 “From the very first frame to the last frame … At no moment may either doll have long loose hair”。第 2 次从第一帧起就是双马尾。
5. **开场和结尾用同一张参考图。**
   - clip3（96 credits）一次成功：群舞里每个娃娃都换成了双马尾，「A2O LITE」字样也保留得很准。
   - clip1（80 credits）有三个问题：开场单人娃娃前 0.9 秒还是长发；字样被抹掉，只剩一层淡淡的残影，位置也不对；推镜比原片松。
   - 只重做开场这个镜头（0–81 帧，3 秒，48 credits），提示词要求去掉字样。结果从第一帧起就是双马尾，画面干净，但推镜又比原片紧（见复盘）。
6. **对齐到原片的帧。**
   - Kling 输出 24 fps，成片脚本按时间戳重采样到 30 fps，再按帧数裁剪或补齐。
   - 测出来 Kling 的输出固定晚 1–2 帧：clip2 第 2 次和 clip3 都是 +2 帧，每个窗口一致；clip1 按切点算是 +1 帧（2.79 秒对 2.73 秒，3.667 秒那个切点正好对上）。
   - 一开始用运动能量做互相关，结果在 −15 到 +20 帧之间乱跳：舞蹈每半拍（约 14 帧）重复一次，相关峰会落到相邻的重复上。改成只比较画面下方 40%（腿和裤子，发型编辑不会动到这里）的像素差，每 1 秒一个窗口，结果就稳定了。
7. **补回被抹掉的叠加元素。** Kling 把原作者签名（每一帧左上角）和开场的「A2O LITE」字样都抹掉了。两者都从视频 A 自己的像素里取回来，只叠在 Kling 生成的帧上：
   - 用灰度闭运算（9×9）把细的深色笔画“填平”，得到背景亮度；原像素比背景暗多少，就是笔画的覆盖度。这样连抗锯齿的边缘也和原片一样。
   - 签名取第 95 帧（浅色背景）。字样第 12 帧起是静止的，取第 30 帧；前 12 帧是闪入动画，逐帧提取。
8. **音轨。**
   - 用 MV 原声，延后 0.0407 秒（48 kHz 下 1954 个采样点）。
   - 沿用 [NEON ×3](../2026-10-22-01-neon-three-universes/) 的设置：整体降 3.5 dB，限幅 −1.4 dB，结尾淡出 0.4 秒，AAC 256 kbps。结果 −14.0 LUFS，真峰值 −1.0 dBTP。
9. **验证。**
   - 成片 690 帧，正好 23.000 秒。
   - 成片音频对视频 A 原音轨的偏差是 5 ms。
   - 画面按 1 秒窗口和视频 A 逐帧比较：双人舞和群舞全程在 ±1 帧以内，手部和图形段与原片完全一致。
   - 用仓库里的 `materials/kling/` 重新合成，得到的文件和成片 SHA-256 相同。

复现：

```bash
bash scripts/prepare_uploads.sh "<视频 A>.mp4" uploads/        # 送去 Kling 的片段（已经生成过就不用再跑）
python scripts/assemble_twin_tails.py "<视频 A>.mp4" "A2O LITE 'NEON' Official Video.mkv" materials/kling NEON_双马尾_23s.mp4 \
    --shift shot1=1 --shift clip1=1 --shift clip2=2 --shift clip3=2
```

## 复盘

**做得好**
- **改原片，不重新生成。** 视频 A 已经和 MV 同步，视频编辑又不动时间轴，所以“动作和节奏与真人片段同步”这一条基本是现成的，只需要把 Kling 的 1–2 帧延迟量出来去掉。
- **只花在有头发的地方。** 手部和图形段直接用原片，上传按整秒补齐，先用最难的一段测试，再决定其余的怎么跑。
- **用上一次结果里的好帧当参考图。** 第一次测试的后半段已经是想要的样子，把它当成 `@Image1`，后面四次都是从第一帧起就变成双马尾。
- **每次运行前先报价。** 每次都先报价、得到确认再运行，再加上一个固定的上传和下载流程，最后五次一共 512 credits。
- **量出来，不靠眼睛。** 帧对齐、音频偏差、响度都有数字，最后还用仓库里的素材重新合成，核对了 SHA-256。

**踩坑 / 注意**
- **通道比模型更容易卡住：** Sora API 已停用；Weave 认的是 Claude 里 Figma 连接器登录的账号；Weave 免费版不能用视频模型。前面一大半时间花在这些上。
- **Weave 上传：** `weave_upload_asset` 在 Claude Code 里不会弹出选择文件的窗口，只返回一个上传地址和令牌。令牌要放在 `Authorization: Bearer` 请求头里，不是表单字段，而且几分钟就过期，所以每次上传前都要重新要一个。
- **没给参考图时，Kling 只在甩头发的瞬间改发型。** 静止的头发会一直保持原样，所以要给参考图，并且在提示词里写明“从第一帧起”。
- **Kling 会抹掉画面上的文字和签名。** 写了“保留”也没用，有时还会留下错位的残影。更稳的做法是让它直接抹干净，再从原片把这些元素补回去。
- **Kling 不严格照原片推镜。** clip1 比原片松；重做时提示词写了 “extreme close-up”，被照字面执行，又推得太紧，1.7–2.7 秒的特写把双马尾切出了画面，最后接受了这一版。浅色背景的双人镜头，原片的浅薄荷色也被改成了暖灰。
- **舞蹈片段不要用运动能量互相关来测延迟：** 动作每半拍重复一次，会对到错的拍子上。比较不受编辑影响的区域的像素，按窗口取中位数。

**下次可以试**
- 用 1080p（每秒 24 credits）重跑一段，对比 720p 放大的画质。
- 取景要写具体：比如“结束时两个娃娃从头顶到腰都在画面里，发圈完整”，不要写“特写”。
- 把“量帧延迟 + 补回叠加元素”抽成通用工具，以后其他 AI 视频编辑也能用。
- 换一种做法对比：Kling Motion Control（约 164 credits）直接用 MV 的真人动作驱动双马尾娃娃，看看同步和画风能保住多少。
