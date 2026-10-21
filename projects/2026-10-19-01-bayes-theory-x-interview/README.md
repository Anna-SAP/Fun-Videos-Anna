# 2026-10-19 · 《非常贝叶斯》理论解析 × 访谈实录

| 项 | 内容 |
|---|---|
| 日期 | 2026-10-19 |
| 类型 | 解说 + 证据插入剪辑（竖屏） |
| 工具 | **骨架：** Gemini Notebook 生成的《非常贝叶斯》（画面水印 + 片尾卡，元数据 `encoder=Google`）<br>**剪辑：** Claude（对话里完成，在电脑上的沙盒里跑 Python / Pillow / ffmpeg） |
| 输入 | 骨架：[`materials/very-bayesian_theory.mp4`](materials/very-bayesian_theory.mp4)（入库）<br>证据：`clip_贝叶斯.mp4`，YouTube 录屏，访谈《Zuckerberg's $100 Billion Bet》片段，104.7 MB，**不入库** |
| 产出 | 1 条成片 + [剪辑脚本](edit-script.md)；另有 1 条 64 秒的[对照版](variants/alt-64s/)（制作工具待确认） |
| 对话 | claude.ai「贝叶斯理论短视频创作」，已加入本 Project |

## 成片

| 预览 | 文件 | 时长 | 规格 | 大小 |
|---|---|---|---|---|
| <img src="thumbs/bayes_theory-x-interview_poster.jpg" width="120"> | [`media/bayes_theory-x-interview.mp4`](media/bayes_theory-x-interview.mp4)<br>原名：非常贝叶斯_理论解析x访谈实录.mp4 | 2:08.2 | 1080×1920 · 30 fps · H.264 CRF 19 · AAC 192 kbps · -14.8 LUFS | 46.9 MB |

逐帧预览：[sheet](thumbs/bayes_theory-x-interview_sheet.jpg)
剪辑脚本（每段在成片里的时间、素材入出点、文案和原话）：[edit-script.md](edit-script.md)

**结构：** 《非常贝叶斯》的旁白贯穿全片，**不在句中切断**。每讲完一个论点，理论动画暂停，切入对应的访谈原片和原声，一共 6 段：

| # | 理论片的说法 | 插入的原话 |
|---|---|---|
| 1 | （开场钩子之后） | “I don't have a huge comparison set”：嘉宾先承认自己能比较的样本有限 |
| 2 | 极具魄力 | “…the true degree of his boldness” |
| 3 | 果断推翻过往、迅速掉头 | “speed and magnitude … change prior actions and pivot” |
| 4 | 像机器一样吸收、刷新 | “ingests new information … fully updates his worldview … newly installed worldview” |
| 5 | 被总结为“非常贝叶斯” | “Very Bayesian. I've never gotten such a nice compliment.” |
| 6 | prior / posterior 双关 | “What lovely priors you have.” → “Posterior.” |

每段插入的画面构成：
- 「访谈实录 n/06」标签，加一句主张标题，关键词标橙色
- 相框里的原始访谈画面：保留英文硬字幕，裁掉播放器边框
- 中英字幕卡
- 「解析」卡：原话关键词 → 中文含义，再加一句点评

理论段左上角有「理论解析」标签。片尾卡是“先看证据，再更新判断。这才是‘非常贝叶斯’”，并配上公式 `P(θ|x) ∝ P(x|θ)·P(θ)`。

## 提示词

见 [prompt.md](prompt.md)。

## 关键制作步骤

1. **盘点素材**
   - 理论片：66.7 秒，720×1280，30 fps，单声道。63.6 秒之后是 Gemini Notebook 的片尾卡。
   - 访谈：YouTube 录屏，带英文硬字幕。开头几秒能看到播放器控件。
2. **用画面拿字幕时间轴，不跑语音识别**（[ASR playbook](../../playbooks/local-asr-timestamps.md) 里记了这种替代做法）
   - 对英文字幕区（`crop=1728:160:96:920`）以 10 fps 取帧，白色像素阈值 200，逐帧做 XOR 差分，找出字幕切换的时刻。
   - 再拼 4 张带时间戳的字幕带拼图人工核对，得到 L1–L21 每句的起止。
3. **停顿与电平**
   - `silencedetect`：理论片用 -35 dB / 0.15 s，访谈用 -38 dB / 0.2 s。
   - 另外做了 50 ms 粒度的 RMS 包络。
4. **复刻风格：** 从理论片的帧里取色，包括纸张底色 `#E8E3D3`、点阵间距（69.5 × 66.8 px）、字幕卡颜色、橙色和青色强调色。叠加的图形都沿用这套样式。
5. **遮挡播放器界面：** 用红色进度条的像素检测出 1.05–4.65 s 有播放器控件。这段时间里用 `drawbox` 盖住进度条，用 `delogo` 去掉右侧的点赞、分享图标。
6. **编写 EDL：** 见 [`scripts/config.py`](scripts/config.py)。
   - `THEORY_SEG`：T1–T8 理论段的入出点
   - `EVIDENCE`：E1–E6 插入段的入出点、音频淡入淡出、对应字幕、解析卡
   - `CAP`：L1–L21 每句的中英文和高亮词
   - `ORDER`：T1 E1 T2 E2 T3 E3 T4 E4 T5 E5 T6 T7 E6 T8 END
7. **生成图形：** [`scripts/make_assets.py`](scripts/make_assets.py)，用 Pillow 画。
   - 纸张底板（颗粒、斑驳、点阵、纤维）
   - 插入段的相框、胶带、标签、字幕卡、解析卡
   - T6 的「严谨注」卡
   - 片尾卡
   - 中文断行规则：标点不出现在行首或行尾，短引号整体保留；字号在 50 / 47 / 44 里自动选
8. **渲染：** [`scripts/render.py`](scripts/render.py)
   - 每段单独渲染成 .mkv（音频为 PCM）。视频按帧数 `trim`、音频按采样点 `atrim`，把音画长度锁死。
   - 插入段开头有 0.18 秒的纸色淡入。
   - 最后用 concat demuxer 拼接，音频转 AAC 192 kbps。
9. **声音：** 用固定增益（旁白 +2.5 dB，访谈 +3.0 dB）加 `alimiter=limit=0.89`（约 -1 dBFS），没有用 loudnorm。成片实测 -14.8 LUFS。
10. **检查**
    - 每段帧数和音频时长是否一致；全片完整解码一遍
    - 拼出各段开头的画面检查
    - 每个切点前后 ±0.4 秒的 RMS
    - 最终 ebur128 测响度
11. **删改与校正**
    - 去掉了 Gemini Notebook 片尾。
    - 原图把 Prior 标成“先验偏见”，在 T6 叠了一张「严谨注」：先验是看到新证据之前的信念，不等于偏见。
    - 中文对照是重新翻译的。分不清“Very Bayesian”“What lovely priors you have”是谁说的，所以字幕不署名。

### 本目录里的脚本

| 文件 | 说明 |
|---|---|
| [`scripts/config.py`](scripts/config.py) | EDL：理论段、插入段、字幕、配色、版式常量 |
| [`scripts/make_assets.py`](scripts/make_assets.py) | 生成全部叠加图层（PNG） |
| [`scripts/render.py`](scripts/render.py) | `python3 render.py <SEG\|concat> <video_dir> <work_dir> [out_name]`：逐段渲染，再拼接 |

这三个文件是当时最后一版 `scripts_v7`，原样从电脑上的 `bayes_edit_work/` 收录。字体路径按 Linux 写（Noto Sans CJK、Lato、DejaVu Serif）。

⚠️ **可复现性：** 交付的成片是不同版本脚本渲染的片段拼起来的。T1–T8 和片尾是 v3，E1、E3–E6 是 v6，E2 是 v7。各版之间只改了字幕文字、字号和时间，`render.py` 没变过。要得到严格对应 v7 的成片，需要用 v7 把 15 段全部重渲染一遍再拼接。

## 复盘

**做得好**
- **骨架旁白不切句。** 插入段紧跟在论点后面，观众听到“极具魄力”，马上就看到 boldness 的原话。
- **解析卡做“原话关键词 → 中文”映射。** 理论片的每个说法都能落到原话里的具体词上：魄力 ↔ boldness，吸收、刷新 ↔ ingest / update / install。
- **埋伏笔：** E3 提醒观众“prior 这个词稍后会以‘先验’的身份再出现”，E6 的双关就接得上。
- **给证据定分量：** E1 把“样本有限”放在最前面，提醒观众后面是共事观察，不是统计结论。
- **纠正原片错误：** 原图的“先验偏见”不准确，叠了「严谨注」；说话人分不清就不署名。

**踩坑**
- **往电脑写文件，覆盖不生效**（加了 force 也没用）。最后改成每改一次就写进新文件夹（`scripts_v2` … `scripts_v7`），并用 md5 或标记字符串两边核对。
- **后台进程活不过一次调用**，要用 `setsid … < /dev/null & disown`。实际渲染是按单次调用的时限，分批在前台跑的。
- **成片由多个版本的片段拼成**（见上面的可复现性说明），复盘和重做都不方便。
- **文档和实现不一致：** 剪辑脚本里写“成片整体加限幅”，实际是每段各自限幅。
- **响度标准不统一：** 这条是 -14.8 LUFS，另外两条剪辑作品是 -16 LUFS。

**下次可以改进**
- 当时提出过、没有做的 60 秒以内版本：只保留插入 1、2、6。
- 每次改版都整体重渲染，保证一个脚本版本对应一条成片。
- 统一用 loudnorm 做到 -16 LUFS / -1 dBTP，和其他作品保持一致。
- 对比一下[对照版](variants/alt-64s/)：同样的素材，64 秒、4 段证据、先放原话再出解析图卡，节奏更快，信息密度不同。

## 两个版本对比

| | 本版（Claude 对话） | [对照版](variants/alt-64s/) |
|---|---|---|
| 时长 | 2:08.2 | 1:04.6 |
| 证据段数 | 6 | 4 |
| 骨架 | 理论片原画面 + 原旁白，逐句保留 | 保留中文旁白，理论图解全部重新绘制 |
| 理论校正 | T6 叠「严谨注」：先验≠偏见 | 重画先验 / 似然 / 后验曲线；删掉“日常俚语”那句 |
| 字幕 | 硬字幕（中英） | 硬字幕 + 可编辑的 SRT |
| 响度 | -14.8 LUFS | -16.3 LUFS |
| 大小 | 46.9 MB | 5.6 MB |
