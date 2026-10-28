# 作品索引

目录命名：`YYYY-MM-DD-NN-slug`。按日期排序，`NN` 是当天的序号，`slug` 用小写英文。文档里互相引用时用短名：**贝叶斯**、**NEON**、**AI 意识**、**NEON ×3**、**NEON 双马尾**、**剑来 · 陈平安**。

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

AI 意识  Gemini Notebook 方案三 ─┐
         Gemini Notebook 方案四 ─┴─ Clipchamp ─→《AI有意识吗》─┐
         JRE #2541 访谈整集（第三方，不入库）────────────────┴─→ 访谈实证版（5:41）
```

## 按标签查找

- **证据插入式剪辑**：贝叶斯、AI 意识
- **Gemini Notebook 骨架**：贝叶斯、AI 意识
- **对齐 / 同步**：NEON、NEON ×3（三路闭环 + 拍点网格）、AI 意识（素材拼接分析、分段校准）、NEON 双马尾（AI 编辑后的画面逐帧对齐原片）
- **AI 视频生成 / 编辑**：NEON 双马尾（Kling 4.0 Video Edit 改发型，参考图，补回字样和签名）
- **拍点 / 卡点剪辑**：NEON ×3（130 BPM 网格，按小节编排）、剑来 · 陈平安（101.9 BPM 重拍网格，一拍一刀，最后四分之一拍快闪）
- **竖屏构图**：NEON（分屏）、NEON ×3（三分屏 ↔ 全屏动态版式、主体跟随裁切）、贝叶斯 / AI 意识（相框嵌入）、剑来 · 陈平安（按脸取景，窗口避开硬字幕，甩镜）
- **特效与动态字幕**：NEON ×3（霓虹扫线、扫描线变身）、剑来 · 陈平安（闪白、冲击缩放、RGB 错位、径向模糊、火星粒子、逐字落下的字幕）
- **人物混剪 / 选镜头**：剑来 · 陈平安（逐镜头认人，只用一个角色的镜头和台词）
- **语音识别 / 字幕**：AI 意识（ASR）、贝叶斯（硬字幕像素差分）、剑来 · 陈平安（硬字幕读台词时间，声谱图确认人声起止）
- **事实核对 / 纠错**：AI 意识（原话与骨架不符）、贝叶斯（先验 ≠ 偏见）
- **同题多版本对比**：贝叶斯（2:08 vs 1:04）、NEON（fit vs crop）、NEON ×3（同一段音乐的三个版本）、NEON 双马尾（原版 vs 双马尾，逐镜头对照）
