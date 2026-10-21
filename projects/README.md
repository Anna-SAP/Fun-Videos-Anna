# 作品索引

目录命名：`YYYY-MM-DD-NN-slug`。按日期排序，`NN` 是当天的序号，`slug` 用小写英文。文档里互相引用时用短名：**贝叶斯**、**NEON**、**AI 意识**。

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

## 素材和成片的关系

```
贝叶斯   Gemini Notebook《非常贝叶斯》──────────────┐
         访谈录屏 clip_贝叶斯（第三方，不入库）──────┴─→ 理论解析 × 访谈实录（2:08）
                                                     （另有 64 秒对照版）

NEON     卡通版片段 + 官方 MV（第三方，不入库）────────→ 两版 9:16 分屏

AI 意识  Gemini Notebook 方案三 ─┐
         Gemini Notebook 方案四 ─┴─ Clipchamp ─→《AI有意识吗》─┐
         JRE #2541 访谈整集（第三方，不入库）────────────────┴─→ 访谈实证版（5:41）
```

## 按标签查找

- **证据插入式剪辑**：贝叶斯、AI 意识
- **Gemini Notebook 骨架**：贝叶斯、AI 意识
- **对齐 / 同步**：NEON、AI 意识（素材拼接分析、分段校准）
- **竖屏构图**：NEON（分屏）、贝叶斯 / AI 意识（相框嵌入）
- **语音识别 / 字幕**：AI 意识（ASR）、贝叶斯（硬字幕像素差分）
- **事实核对 / 纠错**：AI 意识（原话与骨架不符）、贝叶斯（先验 ≠ 偏见）
- **同题多版本对比**：贝叶斯（2:08 vs 1:04）、NEON（fit vs crop）
