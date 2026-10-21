# 2026-10-21 · 《AI有意识吗》访谈实证版：科普解析 + 实证实录

| 项 | 内容 |
|---|---|
| 日期 | 2026-10-21 |
| 类型 | 解说 + 证据插入剪辑（竖屏） |
| 工具 | Claude（对话里完成）+ ffmpeg、sherpa-onnx（本地语音识别）、Pillow（图形） |
| 输入 | 骨架：[`materials/ai-consciousness_main.mp4`](materials/)《AI有意识吗》（2:22），由 Gemini Notebook 生成的方案三、方案四经 Clipchamp 拼接而成（**入库**，见 [materials/](materials/)）<br>证据源：*The Joe Rogan Experience* #2541 · Thomas Campbell（[YouTube v2oBLSDCZaY](https://www.youtube.com/watch?v=v2oBLSDCZaY)，2 小时 47 分钟，本地文件 1.16 GB，**不入库**） |
| 产出 | 1 条成片 + 剪辑清单 |
| 同类作品 | [2026-10-19《非常贝叶斯》理论解析 × 访谈实录](../2026-10-19-01-bayes-theory-x-interview/)：同样是“Gemini Notebook 骨架 + 访谈证据”的结构 |
| 对话 | claude.ai「AI意识科普视频制作」，在本 Project 内 |

## 成片

| 预览 | 文件 | 时长 | 规格 | 大小 |
|---|---|---|---|---|
| <img src="thumbs/ai-consciousness_evidence-cut_poster.jpg" width="120"> | [`media/ai-consciousness_evidence-cut.mp4`](media/ai-consciousness_evidence-cut.mp4)<br>原名：AI有意识吗_访谈实证版.mp4 | 5:40.8 | 1080×1920 · 30 fps · H.264 · AAC 48 kHz · 响度 -16 LUFS | 58.9 MB |

逐帧预览：[sheet](thumbs/ai-consciousness_evidence-cut_sheet.jpg)
剪辑清单（插入点、原片时间码、完整双语字幕）：[edit-list.md](edit-list.md)

**结构：** 主视频完整保留作为骨架，在 **片头 + 7 个论证节点 + 片尾** 插入 9 段 Campbell 的原声。每段都有：

- 「访谈实证 n/8」标签和这段要证明的主张
- 16:9 相框里的访谈画面，下方是讲者署名条
- 「解析」卡：一句话说明这段原话佐证了主视频的哪个说法
- 中英双语字幕：中文沿用主视频的字幕框样式，英文原文灰字放在上方

片尾说明卡写明：片中的实验是 Campbell 本人的讲述，未经独立验证。

## 提示词

见 [prompt.md](prompt.md)：原始任务、后续 5 轮交互、提示词拆解，以及一份建议的复用版。

## 关键制作步骤

```
主视频 ─ 中文 ASR + 停顿检测 ─→ 13 个论述句群 ─┐
                                               ├─→ EDL（9 个插入点） ─→ 图形/字幕 ─→ 分段渲染 ─→ 溶解拼接 ─→ QA
访谈源 ─ 本机预处理 ─ 英文词级 ASR ─ 关键词检索 ┘
```

0. **骨架素材**：Gemini Notebook 生成方案三、方案四，Clipchamp 拼成《AI有意识吗》。详见 [materials/](materials/)。
1. **获取访谈素材**（[大文件 playbook](../../playbooks/large-files-and-transfer-limits.md)）
   - 云端访问不了 YouTube，所以由 Anna 把整集下载到本地文件夹。
   - 1.16 GB 超过了单文件 400 MB 的传输上限。[`scripts/prep_jre_source.bat`](scripts/prep_jre_source.bat) 在本机做两件事：抽出一条 16 kHz、单声道、40 kbps 的音轨（约 50 MB），并用 `-c copy -f segment -segment_time 1500` 把视频**无损**切成 7 段，同时生成偏移表 `parts.csv`。
   - 之后只把需要的分段传到云端。
2. **分析主视频**
   - 用 SenseVoice 做中文语音识别（[`scripts/asr_zh.py`](scripts/asr_zh.py)），用 `silencedetect=-35dB:d=0.35` 找停顿，划出 13 个论述句群。
   - 抽帧拼图看画面；采样纸张底色和字幕框颜色，后面复刻风格。
3. **转写访谈**（[本地 ASR playbook](../../playbooks/local-asr-timestamps.md)）
   - 用 Parakeet-TDT 0.6B v2（int8）做英文识别，配 silero VAD，得到**词级时间码**（[`scripts/asr_en.py`](scripts/asr_en.py)）。
   - 先转写最相关的 36:40–66:40，其余部分放后台跑。
   - 再用关键词（remote view / box / spoon / Alexa / shield / ten times …）检索候选原话。
4. **校准时间轴**：把分段视频的音轨和转写音轨做互相关，测得分段画面比转写时间轴晚约 10.7 ms（`AUDIO_OFFSET`）。每个分段的起点都按 `parts.csv` 逐段验证过。
5. **编写 EDL**（[证据插入剪辑 playbook](../../playbooks/evidence-insert-editing.md)）
   - 每段原声记成 `(video_in, video_out, audio_in, audio_out)`：画面比语音多留一点余量，给溶解用；音频只卡讲者本人的话，不带进 Joe 的插话。
   - 主视频的切点用 10 ms 粒度的能量扫描，放在旁白的停顿里。
6. **图形与字幕**（Pillow + Noto Sans CJK SC）
   - 复刻主视频的纸张纹理底板，做出标签、标题、相框、署名条、解析卡这几层。
   - 中文字幕手动断行（用 `|` 标记），避免单字成行。
7. **渲染与拼接**
   - 每段插入单独渲染。同一段原声由多个片段组成时，交替片段放大到 0.9 倍（punch-in），用来掩盖跳剪。
   - 主视频按切点分段，首尾各加 20–30 ms 的微淡入淡出，防止爆音。
   - 全片用 0.4 秒溶解串起来，响度统一到 -16 LUFS（EBU R128）。
8. **检查**
   - 每段插入的音频都重新做一遍语音识别，和字幕逐句核对；所有转场逐帧检查。
   - **事实核对：** 主视频的“人类要苦修几十个小时深度冥想”在原声里找不到，原话是“两三次课程、每次数小时”。解析卡用的是原话，主视频本身没改。
9. **交付**：成片 62 MB，超过往电脑回写单文件 30 MB 的上限。先用文件卡片下载，同时准备了分块 + 双击合并（带 SHA-256 校验）的备用方案。

### 本目录里的脚本

| 文件 | 说明 | 状态 |
|---|---|---|
| [`scripts/prep_jre_source.bat`](scripts/prep_jre_source.bat) | 本机预处理：抽音轨 + 无损分段（没装 ffmpeg 时自动用 winget 安装） | 原样收录，已在 Anna 电脑上运行过 |
| [`scripts/asr_zh.py`](scripts/asr_zh.py) | 中文旁白识别（SenseVoice + VAD） | 归档时重新跑过（[materials](materials/transcripts/) 和贝叶斯理论片的旁白文稿都是用它生成的） |
| [`scripts/asr_en.py`](scripts/asr_en.py) | 英文词级时间码识别（Parakeet-TDT + VAD，流式写 JSONL） | 原会话版本 |
| [`../../tools/av/find_offset.py`](../../tools/av/find_offset.py) | 互相关对齐 / 定位（通用版） | 归档时重写并测试过 |

**没能归档：** `gfx.py`（图形层）、`edl.py`（EDL 数据）、`build.py`（分段渲染）、`assemble.py`（溶解拼接）、`make_join.py`（分块合并），这几个文件的最终版本没有保存下来，原会话的云端工作区已经回收。EDL 的全部数据（时间码和字幕）都保留在 [edit-list.md](edit-list.md) 里。

## 复盘

**做得好**
- **骨架 + 证据**的结构清楚：主视频每提出一个说法，紧接着就是原话佐证，再用解析卡把两者连起来。
- **音频切口只卡讲者本人的话**，画面另留余量做溶解。原声干净，转场也不突兀。
- **词级时间码 + 停顿检测**，切点能精确到旁白的自然停顿。
- **主动核对事实**，发现了 AI 脚本“加戏”的地方，并在片尾写明“未经独立验证”。

**踩坑**
- 云端访问不了 YouTube。最后由 Anna 在本地下载整集，云端再用本地语音识别拿到词级时间码，不依赖平台字幕。
- 源文件 1.16 GB 超过传输上限，靠本机预处理脚本解决：音轨用来分析，视频分段按需传。
- 后台等待渲染的任务被系统超时停掉了 3 次，渲染本身没受影响，但需要手动接着跑完拼接。
- 中间脚本没有随做随存，事后无法完整复现流水线。

**下次可以改进**
- 在提示词里直接给本地源文件，并写明成片时长上限、能不能加片头片尾说明（见 prompt.md 的复用版）。
- 脚本随做随写进本仓库的 `scripts/`，或者存到本地文件夹，不要只留在云端工作区。
- 长任务不要用“等到结束”的阻塞式后台等待，改成按日志事件监控，或者分阶段提交。
- 5:41 是主视频的 2.4 倍长。投短视频平台的话，可以另剪一个只保留 3–4 段证据的约 3 分钟版本。
