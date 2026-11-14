# 作品索引

目录命名：`YYYY-MM-DD-NN-slug`。按日期排序，`NN` 是当天的序号，`slug` 用小写英文。文档里互相引用时用短名：**贝叶斯**、**NEON**、**AI 意识**、**NEON ×3**、**NEON 双马尾**、**剑来 · 陈平安**、**The Moment**、**Hold Me Slowly**、**WinWin 混剪**、**Bring Jensen Back**。

每个作品目录的结构都一样：

```
README.md      作品卡：概况、成片、步骤、复盘
prompt.md      提示词（原样）+ 后续交互 + 拆解 + 复用版
media/         成片（Git LFS）
materials/     自有素材：AI 生成的骨架视频等（Git LFS）+ 旁白文稿
variants/      同一题材的其他版本（可选）
thumbs/        海报帧 + 逐帧预览（普通 Git）
scripts/       这个作品用到的脚本（可选）
```

## 全部视频

| 作品 | 角色 | 文件 | 时长 | 规格 | 大小 | 工具 |
|---|---|---|---|---|---|---|
| [贝叶斯](2026-10-19-01-bayes-theory-x-interview/) | **成片** | `media/bayes_theory-x-interview.mp4` | 2:08.2 | 1080×1920 | 46.9 MB | Claude |
| | 对照版 | `variants/alt-64s/bayes_theory-x-interview_alt-64s.mp4` | 1:04.6 | 1080×1920 | 5.6 MB | 未记录 |
| | 骨架素材 | `materials/very-bayesian_theory.mp4` | 1:06.7 | 720×1280 | 8.6 MB | Gemini Notebook |
| [NEON](2026-10-21-01-neon-cartoon-vs-mv-split/) | **成片** | `media/neon_split_fit.mp4` | 0:23.1 | 1080×1920 | 12.0 MB | Claude |
| | **成片** | `media/neon_split_crop.mp4` | 0:23.1 | 1080×1920 | 14.7 MB | Claude |
| [AI 意识](2026-10-21-02-ai-consciousness-evidence-cut/) | **成片** | `media/ai-consciousness_evidence-cut.mp4` | 5:40.8 | 1080×1920 | 58.9 MB | Claude |
| | 骨架素材 | `materials/ai-consciousness_main.mp4` | 2:22.6 | 1080×1920 | 109 MB | Clipchamp 拼接 |
| | 骨架素材 | `materials/plan3_consciousness-and-vr.mp4` | 1:10.8 | 720×1280 | 8.7 MB | Gemini Notebook |
| | 骨架素材 | `materials/plan4_consciousness-and-vr.mp4` | 1:17.7 | 720×1280 | 9.4 MB | Gemini Notebook |
| [NEON ×3](2026-10-22-01-neon-three-universes/) | **成片** | `media/neon_three-universes.mp4` | 0:24.6 | 1080×1920 | 23.0 MB | Claude |
| [NEON 双马尾](2026-10-24-01-neon-twin-tails/) | **成片** | `media/neon_twin-tails.mp4` | 0:23.0 | 1920×1080 | 16.0 MB | Kling 4.0 Video Edit + Claude |
| | 生成素材 | `materials/kling/shot1_kling4_720p_run1.mp4` | 0:03.0 | 1280×720 | 1.7 MB | Kling 4.0 Video Edit |
| | 生成素材 | `materials/kling/clip1_kling4_720p_run1.mp4` | 0:05.0 | 1280×720 | 2.9 MB | Kling 4.0 Video Edit |
| | 生成素材（未用） | `materials/kling/clip2_kling4_720p_run1.mp4` | 0:09.0 | 1280×720 | 5.5 MB | Kling 4.0 Video Edit |
| | 生成素材 | `materials/kling/clip2_kling4_720p_run2.mp4` | 0:09.0 | 1280×720 | 5.9 MB | Kling 4.0 Video Edit |
| | 生成素材 | `materials/kling/clip3_kling4_720p_run1.mp4` | 0:06.0 | 1280×720 | 5.2 MB | Kling 4.0 Video Edit |
| [剑来 · 陈平安](2026-10-29-01-jianlai-wulei-highlight/) | **成片** | `media/jianlai_wulei-highlight.mp4` | 0:31.6 | 1080×1920 | 54.5 MB | Claude |
| | 加长版 | `variants/60s/jianlai_wulei-highlight_60s.mp4` | 1:00.0 | 1080×1920 | 73.3 MB | Claude |
| [The Moment](2026-11-10-01-the-moment-you-saw-me/) | **成片**（分享版） | `variants/share/the-moment-you-saw-me_share.mp4` | 3:03.0 | 1080×1920 | 39.6 MB | gpt-image-2 + Claude |
| | 歌词版（分享版） | `variants/lyrics/the-moment-you-saw-me_lyrics_share.mp4` | 3:03.0 | 1080×1920 | 39.6 MB | gpt-image-2 + Claude |
| | 光影版（分享版） | `variants/light/the-moment-you-saw-me_light_share.mp4` | 3:03.0 | 1080×1920 | 39.1 MB | gpt-image-2 + Claude |
| [Hold Me Slowly](2026-11-12-01-hold-me-slowly/) | **成片** | `media/hold-me-slowly.mp4` | 1:05.9 | 1080×1920 | 59.3 MB | Claude（程序生成画面） |
| [WinWin 混剪](2026-11-13-01-winwin-mix-transitions/) | **成片** | `media/winwin-mix_smooth.mp4` | 1:09.3 | 1920×1080 | 42.9 MB | Claude |
| [Bring Jensen Back](2026-11-14-01-bring-jensen-back/) | **成片**（第二版） | `media/bring-jensen-back.mp4` | 4:35.2 | 1080×1920 | 178.7 MB | Claude（程序渲染画面，女主为用户提供的抠像） |
| | 分享版（第二版） | `variants/share/bring-jensen-back_share.mp4` | 4:35.2 | 1080×1920 | 68.3 MB | Claude |
| | 第一版 | `variants/v1/bring-jensen-back_v1.mp4` | 4:35.2 | 1080×1920 | 178.8 MB | Claude |

The Moment 的三条原画质版（7.0 Mbps，各约 163 MB）留在本机，没有入库；入库的是从分镜文件单独编码的 1.6 Mbps 分享版。

## 素材和成片的关系

```
贝叶斯   Gemini Notebook《非常贝叶斯》──────────────┐
         访谈录屏 clip_贝叶斯（第三方，不入库）──────┴─→ 理论解析 × 访谈实录（2:08）
                                                     （另有 64 秒对照版）

NEON     卡通版片段 + 官方 MV（第三方，不入库）────────→ 两版 9:16 分屏

NEON ×3  卡通版片段 + 官方 MV + 舞台版片段（第三方，不入库）→ 三版卡拍混剪（24.6 秒）

NEON 双马尾  卡通版片段（第三方，不入库）─ 有头发的镜头 ─ Kling 4.0 Video Edit ─→ 5 段生成素材 ─┐
             卡通版片段的手部、图形镜头 ───────────────────────────────────────────────────┤
             官方 MV 的音轨（第三方，不入库）─────────────────────────────────────────────┴─→ 双马尾版（23.0 秒）

剑来 · 陈平安  《剑来》最新预告（第三方，不入库）─ 只留吴磊的单人镜头、他本人的独白、高潮段配乐 ─→ 竖屏卡点混剪（31.6 秒）
                再加他的第二段独白、更长的高潮配乐 ──────────────────────────→ 60 秒加长版

The Moment  歌曲原曲（第三方，不入库）─ 量 BPM、段落、原样重复和静默 ─┐
            34 张 gpt-image-2 关键帧 + 本机算的景深图（在 work/，不入库）─┴─→ MV（3:03）
            再加歌词文件（第三方，不入库）─ 逐词对齐 ─ 起雾玻璃上的手写字 ──→ 歌词版（3:03）

WinWin 混剪  专人剪辑的混剪（三支 MV 首尾相接，第三方，不入库）─ 找出 3 个接口，重做画面和声音的衔接 ─→ 重剪版（1:09.3）

AI 意识  Gemini Notebook 方案三 ─┐
         Gemini Notebook 方案四 ─┴─ Clipchamp ─→《AI有意识吗》─┐
         JRE #2541 访谈整集（第三方，不入库）────────────────┴─→ 访谈实证版（5:41）
```

## 按标签查找

- **证据插入式剪辑**：贝叶斯、AI 意识
- **Gemini Notebook 骨架**：贝叶斯、AI 意识
- **对齐 / 同步**：NEON、NEON ×3（三路闭环 + 拍点网格）、AI 意识（素材拼接分析、分段校准）、NEON 双马尾（AI 编辑后的画面逐帧对齐原片）、The Moment（成片音轨对原曲互相关，查出 59.5 ms 的错位）
- **AI 视频生成 / 编辑**：NEON 双马尾（Kling 4.0 Video Edit 改发型，参考图，补回字样和签名）
- **AI 关键帧 + 景深视差**：The Moment（34 张 gpt-image-2 关键帧，一张参考像管人物一致，Depth Anything V2 分层运镜，雨和光由程序画）
- **从歌曲出发的 MV**：The Moment（先量 BPM、段落、原样重复和静默，再让结构决定叙事）、Hold Me Slowly（歌词 MV，画面全部程序生成）、Bring Jensen Back（嘻哈 MV：实测鼓型决定三个最大的切；第二版把女主从"摆进去的 MC"改成渗进画面的见证者）
- **拍点 / 卡点剪辑**：NEON ×3（130 BPM 网格，按小节编排）、剑来 · 陈平安（101.9 BPM 重拍网格，一拍一刀，最后四分之一拍快闪）、The Moment（72 BPM，24 fps 下每小节正好 80 帧，硬切都在小节线上）、WinWin 混剪（三首歌各自的速度和调性，转场卡在落拍和重拍上）、Bring Jensen Back（96 BPM，24 fps 下一拍 15 帧；点头和冲击缩放读分离伴奏里实测的底鼓、军鼓）
- **竖屏构图**：NEON（分屏）、NEON ×3（三分屏 ↔ 全屏动态版式、主体跟随裁切）、贝叶斯 / AI 意识（相框嵌入）、剑来 · 陈平安（按脸取景，窗口避开硬字幕，甩镜）
- **特效与动态字幕**：NEON ×3（霓虹扫线、扫描线变身）、剑来 · 陈平安（闪白、冲击缩放、RGB 错位、径向模糊、火星粒子、逐字落下的字幕）、The Moment（挂在变速时钟上的雨粒子；歌词版的起雾玻璃和手写歌词）、Hold Me Slowly（2D 流体里的发光墨字、水面雨纹、光束、副歌的光环）、Bring Jensen Back（盖章式逐字歌词、两端对齐的海报字、划掉 / 涂黑 / 重力掉落 / 倒带消失、LED 点阵墙、波普网格）
- **人物混剪 / 选镜头**：剑来 · 陈平安（逐镜头认人，只用一个角色的镜头和台词）
- **转场 / 衔接设计**：WinWin 混剪（会呼吸的遮幅、甩镜推入、回声残影 + 低音交接、按亮度溶解，声音和画面一起转）、AI 意识（0.4 秒溶解）、NEON ×3（霓虹扫线、扫描线变身）
- **语音识别 / 字幕**：AI 意识（ASR）、贝叶斯（硬字幕像素差分）、剑来 · 陈平安（硬字幕读台词时间，声谱图确认人声起止）、The Moment（whisper-1 词级时间取中位数，句首对着频谱图手工改）、Hold Me Slowly（人声分离 + 5 个本机 Whisper 模型交叉听写、候选打分、强制对齐，校对一份识别出来的 SRT）、Bring Jensen Back（Demucs 分离人声，中英混唱按字 / 按词强制对齐，每个单位 12 个估计取中位数）
- **事实核对 / 纠错**：AI 意识（原话与骨架不符）、贝叶斯（先验 ≠ 偏见）
- **同题多版本对比**：Bring Jensen Back（第一版 MC vs 第二版见证者，同一时刻对照）、贝叶斯（2:08 vs 1:04）、NEON（fit vs crop）、NEON ×3（同一段音乐的三个版本）、NEON 双马尾（原版 vs 双马尾，逐镜头对照）、剑来 · 陈平安（31.6 秒 vs 60 秒加长版）、The Moment（原版 vs 歌词版，镜头和剪辑点相同）
