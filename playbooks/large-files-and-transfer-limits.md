# 大文件与传输限制

视频文件动辄几百 MB，每个环节都有体积上限。先弄清楚瓶颈在哪一环，再选对应的绕行办法。

## 各环节的上限（2026-10 实测 / 文档）

| 环节 | 上限 | 影响 |
|---|---|---|
| 电脑 → Claude 云端工作区（传入） | 单文件 ≤ 400 MB，单次 ≤ 500 MB | JRE 整集 1.16 GB 传不上来 |
| Claude 云端工作区 → 电脑（写回） | 单文件 ≤ 30 MB | 62 MB 的成片写不回文件夹 |
| 云端工作区访问外网 | 白名单制：YouTube、GitHub LFS 存储都**不通** | 不能直接下载 YouTube；不能从云端上传 LFS |
| GitHub 普通文件 | 超过 50 MB 警告，**超过 100 MB 拒收** | 109 MB 的拼接版必须走 LFS |
| GitHub LFS（Free 个人账户） | 每个计费周期 10 GiB 存储 + 10 GiB 流量 | 本库目前约 287 MB，余量充足 |

## 对策

### 源片太大，传不进云端
**本机预处理，只传需要的部分。** AI 意识那条的 [`prep_jre_source.bat`](../projects/2026-10-21-02-ai-consciousness-evidence-cut/scripts/prep_jre_source.bat) 双击运行就行：

```bat
ffmpeg -i "%SRC%" -vn -ac 1 -ar 16000 -c:a aac -b:a 40k jre_parts\jre_audio.m4a
ffmpeg -i "%SRC%" -map 0:v:0 -map 0:a:0 -c copy -f segment -segment_time 1500 ^
       -reset_timestamps 1 -segment_list jre_parts\parts.csv jre_parts\part_%%02d.mp4
```

- **音轨代理：** 2 小时 47 分钟的音轨压到约 50 MB，足够做语音识别和定位。
- **无损分段：** `-c copy` 只切不转码，几十秒就能完成。`parts.csv` 记录每段的起点，用来把整片时间换算成分段时间。
- 选好片段后，只传用到的那几段（每段 120–180 MB）。

### 成片太大，写不回文件夹
1. 先用对话里的文件卡片下载。
2. 或者分块写回（每块 ≤ 28 MB），附一个双击合并的 `.bat` → `.ps1`。合并后校验 SHA-256，通过才删掉分块。

### 视频要进 GitHub
- 全部走 **Git LFS**（规则见 [`.gitattributes`](../.gitattributes)）。
- 因为云端连不上 LFS 存储，**视频从本机推送**：[`tools/publish_videos_lfs.bat`](../tools/publish_videos_lfs.bat)，按 [`tools/video-manifest.csv`](../tools/video-manifest.csv) 逐个校验后上传。
- 文档、脚本、缩略图都是小文件，从云端或本机推送都可以。

### 往电脑写文件的坑（贝叶斯那次遇到）
- 用桥接工具写回一个**已存在**的文件时，曾经出现覆盖没生效的情况，加了 force 也一样。稳妥的做法是每次改版都写进**新的文件名或文件夹**（`scripts_v2` … `scripts_v7`），写完两边用 md5 核对。
- 在电脑的沙盒 shell 里，后台进程活不过一次调用。需要 `setsid nohup … < /dev/null & disown`，或者把长任务拆成多批前台跑。

### 从源头减小体积
- 按原分辨率导出，不要上采样。《AI有意识吗》拼接版从 720p 升到 1080p，两段合计约 18 MB 的素材导出后变成了 109 MB。
- 归档用 CRF 18–20 的 H.264 就够了。不需要的话，不保留无损中间文件（`.mov` / PCM）。
