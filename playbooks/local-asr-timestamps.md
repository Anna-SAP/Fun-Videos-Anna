# 本地语音识别与时间码

**适用场景：**
- 需要知道“哪句话在第几秒”，用来选片、定切点、对字幕。
- 平台字幕拿不到（云端访问不了 YouTube），或者时间码不够精确。

## 选型（sherpa-onnx，CPU 即可）

| 语言 | 模型 | 输出 | 用在哪里 |
|---|---|---|---|
| 中文旁白 | `sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17`（int8） | 句段级时间码 | AI 意识：主视频节点划分、骨架旁白文稿；贝叶斯：理论片旁白文稿 |
| 英文访谈 | `sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8` | **词级（token）时间码** | AI 意识：选原话、定切点、核对字幕 |
| 断句 | `silero_vad.onnx` | 语音段 | 两种都配 VAD 切段 |

```bash
pip install --break-system-packages sherpa-onnx soundfile
# 模型都在 GitHub releases：k2-fsa/sherpa-onnx → asr-models
ffmpeg -i in.mp4 -ac 1 -ar 16000 in16k.wav
python3 asr_zh.py in16k.wav out.json          # AI 意识 scripts/
python3 asr_en.py in16k.wav out.jsonl 8       # 流式写 JSONL，可以边跑边检索
```

## 工作流要点

1. **先跑重点区间。** 2 小时 47 分钟的访谈，先转写最相关的 30 分钟，其余放后台。拿到一部分结果就能开始选片。
2. **关键词检索候选原话。** 比如 `remote view / box / spoon / Alexa / shield / ten times`，把命中的句子连同时间码列出来再人工挑。
3. **定切点：** 用词级时间码确定一句话的起止；再用 10 ms 粒度的能量扫描，在停顿里找最安静的点下刀。
4. **停顿检测（主视频）：** `ffmpeg -i main16k.wav -af silencedetect=noise=-35dB:d=0.35 -f null -`
5. **复核：** 插入片段渲染完后再识别一次，和字幕逐句对照，能发现切掉半个词、字幕错位这类问题。

## 没有 ASR 时：从硬字幕拿时间轴

素材本身带烧录字幕（比如 YouTube 录屏）时，可以不跑语音识别，直接从画面里读出字幕的切换时间。[贝叶斯](../projects/2026-10-19-01-bayes-theory-x-interview/)那条就是这样做的：

1. 只取字幕所在的横条：`ffmpeg -i clip.mp4 -vf "fps=10,crop=1728:160:96:920,scale=960:80,format=gray" -f rawvideo -`
2. 白色像素（> 200）做成掩膜，每帧和前一帧做 XOR，差异像素超过阈值的地方就是换字幕。
3. 再按时间窗拼几张字幕带拼图（`fps=4,…,tile=4x19`），人工读出每句的英文原文和起止时间。

字幕时间就是原片的时间，不会有 ASR 断句不准的问题；缺点是英文要人工抄录。

## 已知问题

- **中文同音字：** SenseVoice 会把“遥视”识别成“姚氏 / 摇视”，“低熵”识别成“低商”，“缓冲层”识别成“缓冲草”。视频有硬字幕时，**用画面字幕校正**（AI 意识和贝叶斯的旁白文稿都是这样做的）；没有字幕时，按术语表替换。
- 识别结果只能当检索和定位工具。成片字幕要人工审校，译文要对照原话。

## 歌词逐字时间：两个对齐器互相校验

[门没开，灯没关 · melody1](../projects/2026-11-17-02-bring-jensen-back-door-light/) 里用的做法。已知歌词、要每个字的起点时，不要只信一个强制对齐器，两种原理的错法不一样：

| | 怎么对齐 | 准的地方 | 错的地方 |
|---|---|---|---|
| Whisper（faster-whisper 的 `find_alignment`） | 交叉注意力 + DTW | 一句从哪开始、到哪结束 | 把一个词的几个字放在同一瞬间；句首偏早 |
| MMS 对齐模型（`torchaudio.pipelines.MMS_FA`，汉字先转无声调拼音） | CTC 逐帧后验 + Viterbi | 说唱里音节的间距 | 每句第一个和最后一个字会漂进相邻的句子；一有合唱就失灵（路径的平均后验掉到 0.05 以下） |

```bash
pip install --break-system-packages torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install --break-system-packages pypinyin
python3 scripts/align.py     lyrics.txt map.json       align_raw.json   # Whisper，每个字 12 个估计
python3 scripts/ctc_align.py lyrics.txt align_raw.json align_ctc.json   # CTC，每个字 12 个估计
python3 scripts/timing.py    lyrics.txt align_raw.json align_ctc.json lyric_timing.json --report
python3 scripts/qc_strips.py lyric_timing.json work/qc/q 24-31           # 把结果画回频谱图上看
```

合并规则：两者相差 0.09 秒以内的字当锚点；说唱段里锚点之间的字按音节均匀分布；旋律段以 Whisper 为主；句首用 Whisper；最后吸附到人声轨上最近的起音峰。

三条自检，都抓到过真问题：

1. **相邻两句不能重叠。** 抓到过两个对齐器同时把下一句的开头放进上一句里（差 0.7 秒）。
2. **每句的起点相对小节线的位置应该缓慢变化。** 同一段里某一句突然差出半拍，多半是错的；副歌每遍的起点应该正好差一小节。
3. **量出来的速度拿"一句歌词多长"核对。** trap 的三连音 hi-hat 会把自相关带到真实速度的 5/6。

试过但没有采用：把每个字用动态规划分配给检测到的起音峰。在手工核对过的 142 个字上，平均误差和原方法一样（0.16 秒），说明难的地方缺的是信息而不是算法，只能对着频谱图看。
