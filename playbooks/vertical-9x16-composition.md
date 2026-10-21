# 竖屏 9:16 构图

**适用场景：** 横屏 16:9 素材要放进 1080×1920 竖屏，比如上下分屏对比，或者在解说视频里嵌入访谈画面。

## 三种做法

| 做法 | 画面 | 适合 | ffmpeg 要点 |
|---|---|---|---|
| **完整画面 + 模糊填充（fit）** | 16:9 完整保留，空白处填同一画面的模糊放大版 | 需要看清全部内容，比如群舞、字幕、边缘的人 | `split` 两路：前景 `scale=1080:-2`；背景 `scale=W:H:force_original_aspect_ratio=increase,crop=W:H,gblur=sigma=28,eq=brightness=-0.06`；`overlay=(W-w)/2:(H-h)/2` |
| **铺满裁切（crop）** | 居中裁切铺满 | 主体在画面中央，追求冲击力 | `scale=W:H:force_original_aspect_ratio=increase,crop=W:H` |
| **相框嵌入** | 16:9 放进设计好的底板 | 解说 + 证据：底板上还要放标题、解析卡和字幕 | 底板 PNG + `overlay=x:y`；画面 `scale=1000:562` |

项目 02 的上下分屏就是每半屏 1080×960，最后 `vstack`。脚本：[`render_split_9x16.sh`](../projects/2026-10-21-02-neon-cartoon-vs-mv-split/scripts/render_split_9x16.sh)

## 细节清单

- **统一帧率：** 23.976 fps 和 30 fps 的素材先都过 `fps=30`，再 `setsar=1`，避免 vstack 报错或者画面变形。
- **缩放算法：** 放大时用 `flags=lanczos`。
- **音轨：** 选音质最好、时长完整的一路（项目 02 用了 MV 原声，没用 74 kbps 的卡通版音轨），结尾 `afade` 淡出 0.4 秒。
- **编码：** `libx264 -preset slow -crf 18 -profile:v high -pix_fmt yuv420p -movflags +faststart`，AAC 192 kbps。
- **安全区：** 竖屏平台的底部（大约最后 10–20%）和右侧常被标题、按钮挡住，各平台不一样。项目 03 为了和主视频一致，字幕框放在底部（底边 y=1810），**投放到有底部遮挡的平台前，要先确认字幕会不会被挡住**。
- **标注：** 对比类视频最好在每半屏加一个小角标（比如“AI 卡通版 / 原版 MV”），观众不用猜哪边是哪边。
