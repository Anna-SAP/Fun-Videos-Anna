# 学习轨迹

按时间记录每个作品带来的新能力和关键收获。细节在各作品页，可复用的方法在 [playbooks](../playbooks/)。

## 时间线

| 日期 | 作品 | 新学会 / 新尝试 | 关键收获 |
|---|---|---|---|
| 2026-10-19 | [贝叶斯 · 理论解析 × 访谈实录](../projects/2026-10-19-01-bayes-theory-x-interview/) | 第一次做“Gemini Notebook 骨架 + 访谈证据”；用硬字幕像素差分拿时间轴；EDL（config.py）驱动的分段渲染；同一题材另有一个 64 秒的对照版 | 骨架旁白不切句，论点后紧跟原话；骨架里的术语错误用「严谨注」纠正；改版要整体重渲染，否则成片由多个版本拼成 |
| 2026-10-21 | [NEON · 卡通版 vs 原版分屏](../projects/2026-10-21-01-neon-cartoon-vs-mv-split/) | 用音频互相关做毫秒级对齐；竖屏分屏的两种适配方式 | AI 重绘会改画面，不会改节拍，所以用音频做对齐基准；先全局粗定位，再滑窗复核 |
| 2026-10-21 | [AI 意识 · 访谈实证版](../projects/2026-10-21-02-ai-consciousness-evidence-cut/) | 用 Gemini Notebook 生成多个“方案”，再在 Clipchamp 里拼成骨架；本地 ASR 拿词级时间码；本机预处理 1.16 GB 源片；0.4 秒溶解 + 响度统一 | 同一模式的第二次实践，流程更完整；AI 骨架会“加戏”，要回到原话核对；中间脚本要随做随存 |
| 2026-10-22 | [NEON ×3 · 三个宇宙](../projects/2026-10-22-01-neon-three-universes/) | 第一次在本机 Claude Code 里完成整条流程；三路素材闭环对齐；拟合拍点网格、按小节编排切点；Python 逐帧合成动态版式（三分屏 ↔ 全屏缓动、霓虹扫线、扫描线变身）；暗像素跟拍 | 素材共用一段音乐时，先建一个主时钟，再在上面自由编排；结构跟着歌的段落走；全屏段要逐帧检查取景 |
| 2026-10-21 | 建立本知识库 | Git LFS、manifest 驱动的本机上传脚本 | 云端连不上 LFS 存储，视频从本机推；第三方素材只登记不入库；一个作品 = 一条成片 + 它的素材 |

## 能力地图

| 能力 | 掌握程度 | 在哪用过 |
|---|---|---|
| AI 生成解说骨架（Gemini Notebook） | 会用，已形成固定搭配 | 贝叶斯、AI 意识 |
| 在线剪辑拼接（Clipchamp） | 会用 | AI 意识（素材） |
| 证据插入式剪辑 | 做过两次（[playbook](../playbooks/evidence-insert-editing.md)） | 贝叶斯、AI 意识 |
| ffmpeg 滤镜图：缩放、裁切、模糊填充、vstack、tpad、adelay、xfade、drawbox、delogo、ebur128 | 能写 | 全部 |
| 音频互相关对齐 | 能复用（[playbook](../playbooks/audio-sync-cross-correlation.md) + [工具](../tools/av/find_offset.py)） | NEON、AI 意识、NEON ×3（三路闭环） |
| 拍点检测与卡拍剪辑 | 做过一次（[playbook](../playbooks/audio-sync-cross-correlation.md#拍点网格让切点卡在节拍上)） | NEON ×3 |
| 动态版式与主体跟随裁切（Pillow + numpy 逐帧合成） | 做过一次（[playbook](../playbooks/vertical-9x16-composition.md#动态版式三分屏--全屏neon-3)） | NEON ×3 |
| 本地语音识别 / 硬字幕读时间轴 | 能复用（[playbook](../playbooks/local-asr-timestamps.md)） | AI 意识、贝叶斯 |
| 程序化图形与字幕（Pillow） | 做过两次；贝叶斯的脚本已归档 | 贝叶斯、AI 意识 |
| 大文件流转（分段、代理、分块合并、LFS） | 能复用（[playbook](../playbooks/large-files-and-transfer-limits.md)） | AI 意识、归档 |

## 下一步想试

- 贝叶斯：做当时提出过的 60 秒以内版本（只保留插入 1、2、6），和 64 秒对照版比一比
- AI 意识：再剪一个约 3 分钟的短版（3–4 段证据）
- NEON：给分屏加“AI 卡通版 / 原版 MV”角标（NEON ×3 已经加上了版本角标，旧的分屏还没加）
- NEON ×3：出一个不带文字的纯净版；把版式引擎抽成通用工具
- 两条访谈实证版统一用 -16 LUFS；在提示词里先定总时长和证据段数
- 补齐 Gemini Notebook 的输入资料和指令，比较同一份资料用不同指令生成的效果
