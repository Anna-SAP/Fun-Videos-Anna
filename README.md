# Fun Videos · Anna

> 记录我用 AI 做科普 / 趣味短视频的学习过程：每个作品的**成片、素材、生成提示词、关键制作步骤和复盘**，以及从中沉淀下来、下次能直接用的**方法和脚本**。

<table>
<tr>
<td align="center"><a href="projects/2026-10-19-01-bayes-theory-x-interview/"><img src="projects/2026-10-19-01-bayes-theory-x-interview/thumbs/bayes_theory-x-interview_poster.jpg" width="150"></a><br><sub>贝叶斯 · 理论解析 × 访谈实录</sub></td>
<td align="center"><a href="projects/2026-10-21-01-neon-cartoon-vs-mv-split/"><img src="projects/2026-10-21-01-neon-cartoon-vs-mv-split/thumbs/neon_split_fit_poster.jpg" width="150"></a><br><sub>NEON · 卡通版 vs 原版分屏</sub></td>
<td align="center"><a href="projects/2026-10-21-02-ai-consciousness-evidence-cut/"><img src="projects/2026-10-21-02-ai-consciousness-evidence-cut/thumbs/ai-consciousness_evidence-cut_poster.jpg" width="150"></a><br><sub>AI 意识 · 访谈实证版</sub></td>
</tr>
</table>

## 作品

| 日期 | 作品 | 做了什么 | 骨架素材 | 剪辑 |
|---|---|---|---|---|
| 2026-10-19 | [《非常贝叶斯》理论解析 × 访谈实录](projects/2026-10-19-01-bayes-theory-x-interview/) | 在理论解析片的论点之后插入 6 段扎克伯格访谈原话，配解析卡和「严谨注」，成片 2:08 | Gemini Notebook | Claude |
| 2026-10-21 | [NEON：AI 卡通版 vs 官方 MV](projects/2026-10-21-01-neon-cartoon-vs-mv-split/) | 用音频互相关精确对齐，做成 9:16 上下分屏（两种适配方式） | —（第三方素材） | Claude |
| 2026-10-21 | [《AI有意识吗》访谈实证版](projects/2026-10-21-02-ai-consciousness-evidence-cut/) | 在科普短片的 9 个节点插入 JRE #2541 访谈原声，配双语字幕和解析卡，成片 5:41 | Gemini Notebook + Clipchamp | Claude |

工作模式基本固定为：**Gemini Notebook 生成解说骨架 → Claude 插入一手证据、核对事实、合成成片**。完整清单（每条视频的规格、大小、角色）见 [projects/README.md](projects/README.md)。

## 方法沉淀（playbooks）

| | |
|---|---|
| [证据插入式剪辑](playbooks/evidence-insert-editing.md) | 骨架 + 原声的完整流程，以及两次实践的对比 |
| [音频互相关对齐](playbooks/audio-sync-cross-correlation.md) | 毫秒级对齐两段视频；判断一段素材是从哪里剪出来的 |
| [本地语音识别与时间码](playbooks/local-asr-timestamps.md) | 中文旁白、英文词级时间码；没有 ASR 时从硬字幕读时间轴 |
| [竖屏 9:16 构图](playbooks/vertical-9x16-composition.md) | 完整画面 + 模糊填充 / 铺满裁切 / 相框嵌入 |
| [大文件与传输限制](playbooks/large-files-and-transfer-limits.md) | 源片太大、成片写不回、GitHub 100 MB 限制、写回文件的坑 |
| [提示词模式](playbooks/prompt-patterns.md) | 视频任务提示词该写什么，哪些漏写会返工 |

学习时间线和能力地图：[docs/learning-log.md](docs/learning-log.md)

## 仓库结构

```
.
├── README.md                  ← 你在这里
├── projects/                  每个作品一个目录：YYYY-MM-DD-NN-slug/
│   ├── README.md              作品索引
│   └── <作品>/
│       ├── README.md          作品卡：概况 · 成片 · 步骤 · 复盘
│       ├── prompt.md          提示词原文 · 后续交互 · 拆解 · 复用版
│       ├── media/             成片（Git LFS）
│       ├── materials/         自有素材，比如 AI 生成的骨架视频（Git LFS）及其旁白文稿
│       ├── variants/          同一题材的其他版本（可选）
│       ├── thumbs/            海报帧 + 逐帧预览
│       └── scripts/           这个作品用到的脚本
├── playbooks/                 跨作品可复用的方法
├── tools/
│   ├── av/                    find_offset.py（对齐）、contact_sheet.sh（缩略图）
│   ├── video-manifest.csv     视频清单：仓库路径 ↔ 本地文件名 + SHA-256
│   └── publish_videos_lfs.*   在本机把视频经 Git LFS 推上来
├── templates/project/         新作品模板
└── docs/
    ├── storage-policy.md      什么入库、怎么入库（LFS）、第三方素材登记
    └── learning-log.md        学习轨迹
```

## 新增一个作品

1. 复制 `templates/project/` 到 `projects/YYYY-MM-DD-NN-slug/`
2. 在 `prompt.md` 里原样粘贴提示词和后续交互
3. 在 `README.md` 里写步骤和复盘；用 `tools/av/contact_sheet.sh` 生成缩略图
4. 在 `tools/video-manifest.csv` 里给成片和自有素材各加一行，然后在本机双击 `publish_videos_lfs.bat` 上传
5. 更新本页的作品表、`projects/README.md` 和 `docs/learning-log.md`；有可复用的方法就补进 `playbooks/`

## 克隆

视频用 Git LFS 存储（[说明](docs/storage-policy.md)）：

```bash
git lfs install
git clone https://github.com/Anna-SAP/Fun-Videos-Anna.git
# 只要文档、不下载视频：
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Anna-SAP/Fun-Videos-Anna.git
```

## 素材与版权

本库只用于个人学习记录。第三方原始素材（访谈整集、访谈录屏、官方 MV、其他创作者的作品）**不入库**，只在 [docs/storage-policy.md](docs/storage-policy.md) 里登记来源。部分成片含有这些素材的片段，版权归原作者所有。
