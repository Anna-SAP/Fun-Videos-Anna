# 学习轨迹

按时间记录每个作品带来的新能力和关键收获。细节在各项目页，可复用的方法在 [playbooks](../playbooks/)。

## 时间线

| 日期 | 作品 | 新学会 / 新尝试 | 关键收获 |
|---|---|---|---|
| 待补充 | 贝叶斯主题视频（待归档） | 待补充 | 待补充 |
| 2026-10-21 | [01 · Gemini Notebook 生成《意识与虚拟现实的本质》方案三 / 四，Clipchamp 拼成《AI有意识吗》](../projects/2026-10-21-01-gemini-notebook-ai-consciousness/) | 用 AI 一键生成带旁白、图示、硬字幕的竖屏科普短片；生成多个“方案”再挑选拼接 | AI 脚本会“加戏”，事实要回到一手来源核对；导出时不要上采样 |
| 2026-10-21 | [02 · NEON 卡通版 vs 官方 MV 9:16 分屏](../projects/2026-10-21-02-neon-cartoon-vs-mv-split/) | 用音频互相关做毫秒级对齐；竖屏分屏的两种适配方式 | AI 重绘会改画面，不会改节拍，所以用音频做对齐基准；先全局粗定位，再滑窗复核 |
| 2026-10-21 | [03 · 《AI有意识吗》访谈实证版](../projects/2026-10-21-03-ai-consciousness-evidence-cut/) | 本地语音识别拿词级时间码；EDL 驱动的程序化剪辑；证据卡、双语字幕；本机预处理大文件 | 骨架 + 证据 + 解析的结构；切点放在停顿里，音频只卡讲者原话；中间脚本要随做随存 |
| 2026-10-21 | 建立本知识库 | Git LFS、manifest 驱动的本机上传脚本 | 云端连不上 LFS 存储，视频从本机推；第三方素材只登记不入库 |

## 能力地图

| 能力 | 掌握程度 | 在哪用过 |
|---|---|---|
| AI 生成科普短片（Gemini Notebook） | 会用 | 01 |
| 在线剪辑拼接（Clipchamp） | 会用 | 01 |
| ffmpeg 滤镜图：缩放、裁切、模糊填充、vstack、tpad、adelay、xfade、ebur128 | 能写 | 02 · 03 |
| 音频互相关对齐 | 能复用（[playbook](../playbooks/audio-sync-cross-correlation.md) + [工具](../tools/av/find_offset.py)） | 01 · 02 · 03 |
| 本地语音识别（sherpa-onnx） | 能复用（[playbook](../playbooks/local-asr-timestamps.md)） | 01 · 03 |
| 程序化图形与字幕（Pillow） | 做过一次，脚本未保存 | 03 |
| 证据插入式剪辑 | 做过一次（[playbook](../playbooks/evidence-insert-editing.md)） | 03 |
| 大文件流转（分段、代理、分块合并、LFS） | 能复用（[playbook](../playbooks/large-files-and-transfer-limits.md)） | 03 · 归档 |

## 下一步想试

- 给项目 02 的分屏加“AI 卡通版 / 原版 MV”角标
- 从项目 03 再剪一个约 3 分钟的短版（3–4 段证据），对比两版的节奏
- 补齐项目 01 的 Gemini Notebook 提示词，试一下同一份资料用不同指令生成的效果差异
