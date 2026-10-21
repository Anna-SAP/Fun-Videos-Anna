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
