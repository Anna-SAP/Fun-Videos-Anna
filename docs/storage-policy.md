# 存储策略：什么入库、怎么入库

## 规则

| 内容 | 入库方式 | 位置 |
|---|---|---|
| **成片** | ✅ Git LFS | `projects/<作品>/media/`（同题的其他版本放 `variants/`） |
| **自有素材**（比如 Gemini Notebook 生成的骨架视频、自己拼接的中间版） | ✅ Git LFS | `projects/<作品>/materials/` |
| 缩略图、逐帧预览（jpg，几十 KB） | ✅ 普通 Git | `projects/<作品>/thumbs/` |
| 提示词、制作步骤、复盘、剪辑清单、旁白文稿 | ✅ 普通 Git（Markdown） | `projects/<作品>/` |
| 脚本（.py / .sh / .bat / .ps1） | ✅ 普通 Git | `projects/<作品>/scripts/`，通用的放 `tools/` |
| **第三方原始素材**（访谈整集、访谈录屏、官方 MV、别人的作品） | ❌ 不入库：在作品 README 和下面的登记表里记来源、文件名和体积 | — |
| 中间产物（分段、PCM、渲染缓存、模型文件） | ❌ 不入库（见 [.gitignore](../.gitignore)） | — |

第三方原始素材不入库有两个原因：一是版权不属于自己，二是体积大（JRE 整集 1.16 GB、MV 201 MB）。需要复现时，按项目 README 里记的来源重新获取。

## Git LFS

- 跟踪规则见 [`.gitattributes`](../.gitattributes)：`*.mp4 *.mov *.mkv *.webm *.avi *.m4a *.wav *.mp3 *.flac *.gif`
- **为什么不用普通 Git：** GitHub 单文件超过 100 MB 直接拒收，《AI有意识吗》拼接版有 109 MB。即使在 100 MB 以内，视频提交进 Git 历史后，每次克隆都要下载全部版本，事后要清理只能改写历史。
- **配额：** GitHub Free 个人账户每个计费周期有 10 GiB LFS 存储 + 10 GiB 流量（[GitHub 文档](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)）。本库目前约 350 MB。存储按所有版本累计，同一个视频改版重传会重复占用。

### 视频从本机上传

Claude 的云端工作区连不上 GitHub LFS 的存储服务器（`github-cloud.s3.amazonaws.com`、`lfs.github.com`），所以分成两步：

1. **文档、脚本、缩略图：** 从云端推送（普通 Git）。
2. **视频：** 在 Anna 的电脑上双击 [`tools/publish_videos_lfs.bat`](../tools/publish_videos_lfs.bat)。它会：
   - 检查并安装 Git / Git LFS
   - 克隆或更新仓库
   - 按 [`tools/video-manifest.csv`](../tools/video-manifest.csv) 找到本地视频，校验 SHA-256 后复制到 `media/`
   - **确认每个视频都是 LFS 指针**之后才提交、推送

   这个脚本可以重复运行：已上传的会跳过。

### 新增一个视频

1. 视频放在本机的任一视频文件夹里。上传脚本会依次在这些文件夹里找 `local_file`：放脚本的文件夹（`D:\Downloads_D\科普视频学习与制作`），以及 `%USERPROFILE%\Downloads\Video`（贝叶斯的文件在这里）。要加别的文件夹，就改 `publish_videos_lfs.bat` 里的 `EXTRA_DIRS`，多个文件夹用分号隔开。
2. 在 `tools/video-manifest.csv` 里加一行：

   ```csv
   repo_path,local_file,bytes,sha256,note
   projects/<日期-序号-slug>/media/<英文文件名>.mp4,<本地文件名，可以带子文件夹，用 / 分隔>,<字节数>,<sha256>,<说明>
   ```

   - SHA-256：PowerShell 里运行 `Get-FileHash -Algorithm SHA256 <文件>`；Linux / macOS 用 `sha256sum`。
   - `repo_path` 只用小写英文、数字和连字符，链接才稳定。原中文文件名写在 `local_file` 列和作品 README 里。
3. 提交 manifest 和项目文档，然后在本机运行 `publish_videos_lfs.bat`。

## 克隆本库

```bash
git lfs install
git clone https://github.com/Anna-SAP/Fun-Videos-Anna.git          # 含视频（约 350 MB）
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Anna-SAP/Fun-Videos-Anna.git   # 只要文档
git lfs pull --include "projects/2026-10-19-01-*"                   # 之后按需拉某个项目的视频
```

## 第三方素材登记

| 作品 | 素材 | 来源 | 本地文件 / 体积 |
|---|---|---|---|
| 贝叶斯 | 访谈录屏 | YouTube 播放页录屏，访谈《Zuckerberg's $100 Billion Bet》片段，带英文硬字幕 | `clip_贝叶斯.mp4` / 99.8 MB |
| NEON | 卡通版片段 | Higgsfield 创作者作品（文件名标注 `#higgsfieldcreator … Made @higgsfield.ai`） | `🩵 Comment [neon] 🩵 … Made @higgsfield.ai.mp4` / 3.1 MB |
| NEON | 官方 MV | A2O LITE《NEON》Official Video | `A2O LITE 'NEON' Official Video.mkv` / 201 MB |
| NEON ×3 | 舞台版片段 | 舞台表演片段，画面带「WORLD PREMIERE」字样，具体节目未核实 | `23 secondes A2O_20261022.mp4` / 5.1 MB |
| 剑来 · 陈平安 | 剧集预告 | 《剑来》最新预告（吴磊主演），腾讯视频出品，带中英硬字幕和「腾讯视频」水印 | `吴磊《剑来》最新预告.mp4` / 78.7 MB |
| NEON 双马尾 | 卡通版片段、官方 MV | 同 NEON。卡通版有头发的镜头经 Kling 改了发型，其余镜头原样使用；MV 只用了音轨 | 同上 |
| AI 意识 | 访谈整集 | *The Joe Rogan Experience* #2541 · Thomas Campbell，[YouTube v2oBLSDCZaY](https://www.youtube.com/watch?v=v2oBLSDCZaY) | `Joe Rogan Experience #2541 - Thomas Campbell.mp4` / 1.16 GB |

成片里包含这些素材的片段（NEON 和 NEON ×3 的 MV、卡通、舞台画面，NEON 双马尾的卡通画面和 MV 音轨，两条访谈实证版里的访谈原声，剑来 · 陈平安的预告画面和原声）。NEON 双马尾的 `materials/kling/` 是 Kling 在卡通版画面上改出来的，同样是衍生作品。本库是公开仓库，素材版权归原作者所有，这里只作个人学习记录。
