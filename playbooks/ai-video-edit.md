# AI 视频编辑：只改一个属性，保住原片的时间轴

**适用场景：** 原片的动作、镜头、剪辑和音乐都已经满意，只想改一个属性，比如发型、服装颜色、道具，而且成片要和原来的音轨（或另一个同步版本）保持帧级同步。

**核心思路：** 做视频编辑（video-to-video edit），不重新生成。编辑模型基本不改时间轴，只要把它带来的 1–2 帧延迟量出来去掉，原片和音乐、和其他版本的同步就都保住了。用另一个视频驱动动作重新生成（motion control），镜头、剪辑和同步都得重做。

## 先确认通道和预算

本机没有 NVIDIA 显卡时，视频生成只能用云端服务。在 [NEON 双马尾](../projects/2026-10-24-01-neon-twin-tails/) 时（2026-10）的情况：

| 通道 | 状态 |
|---|---|
| OpenAI Sora 2 / Videos API | 2026-09-24 已停用，没有替代接口 |
| Figma Weave（Claude 的 Figma 连接器自带 `weave_*` 工具） | 认的是**连接器登录的那个 Figma 账号**，要先在 Weave 的个人设置里关联同一个账号。**免费版不能用任何视频模型**；Starter $24/月，1,500 credits |
| Higgsfield / Kling / Runway 网页版 | 可以手动生成，Claude 负责剪辑和对齐 |

Weave 上的视频编辑模型（标价，按默认时长估算，实际以运行前的报价为准）：

| 模型 | 标价 | 输入 | 备注 |
|---|---|---|---|
| **Kling 4.0 Video Edit** | 720p 每秒 16 credits、1080p 每秒 24 credits（实测报价） | 3–30 秒，短边至少 700 px | 支持参考图 `@Image1`；输出 24 fps |
| Kling o1 Edit Video | ~147 | 3–10 秒 | |
| Runway Aleph | ~90 / 次 | | |
| Runway Aleph 2 | ~504 | 2–30 秒 | |
| Wan 2.2 Animate Replace | ~48 | | 替换单个角色，不适合多人和群舞 |

`weave_run_model` 不带 `acknowledgedCost` 调用只报价、不扣费；每次运行（包括重跑）都要先给用户看报价，确认后再运行。

## 上传

`weave_upload_asset` 在 Claude Code 里不会弹出选择文件的窗口，只返回 `submitUrl` 和 `token`：

```bash
curl -s -X POST "<submitUrl>" -H "Authorization: Bearer <token>" \
  -F "file=@clip.mp4;type=video/mp4;filename=clip.mp4"
# → {"id":…, "url":"https://media.weavy.ai/…", "width":1280, "height":720, "fps":30, "duration":9}
```

- 令牌放在**请求头**里。放在表单字段里会返回 401 “Upload token is invalid”。
- 令牌几分钟就过期，每次上传前都重新要一个。
- 返回的整个对象原样传给模型的视频 / 图片输入。

## 准备片段

1. **逐帧找切点**，只送需要改的镜头。不需要改的（比如手部特写、图形段）直接用原片，省 credits，也少一处出问题的地方。
2. **按帧精确剪出**（`trim=start_frame:end_frame`），缩放到模型要求的尺寸（Kling 要求短边至少 700 px，1276×718 → 1280×720）。
3. **最后一帧补到整秒**（`tpad=stop=N:stop_mode=clone`）。Kling 按整秒计费，也按整秒输出；输入长度和请求时长一致时，时间轴不会被拉伸。
4. **先拿最难的一段测试**（动作最大、头发甩得最多的那段），满意了再跑其余的。

脚本：[`prepare_uploads.sh`](../projects/2026-10-24-01-neon-twin-tails/scripts/prepare_uploads.sh)。

## 让改动从第一帧开始

不给参考图时，Kling 只在**甩头发、转身这类大动作的瞬间**改发型，静止的头发会一直保持原样。NEON 双马尾的第一次测试里，一个娃娃到 1.3 秒才变成双马尾，另一个到 4.3 秒才变。

修正方法：

1. 从第一次的结果里挑一帧，要求所有角色都已经是目标样子、画面干净（没有字样残影）。把它当成参考图 `@Image1`。
2. 提示词写明时间范围和禁止项：

```text
Edit @Video1: change ONLY the hairstyle. From the very first frame to the last frame, both dolls must
wear high twin tails exactly like the dolls in @Image1 … At no moment may either doll have long loose
hair. Keep everything else exactly as in @Video1: faces, …, dance motion and timing, camera moves …
```

之后四次都是从第一帧起就变成双马尾。

## 原片上的文字和签名

Kling 会抹掉画面上的文字、Logo 和作者签名，提示词里写了“保留”也不管用，有时还会留下一层错位的淡残影。更稳的做法：

1. 提示词里**直接要求去掉**（`Remove the '…' text overlay … leaving a clean picture`），先得到干净的画面。
2. 从原片自己的像素里把这些元素取回来，只叠在生成的帧上：
   - 用灰度闭运算（`scipy.ndimage.grey_closing`，9×9）把细的深色笔画“填平”，得到背景亮度 B。
   - 覆盖度 `a = clip((B − L) / (B − ink), 0, 1)`，L 是原像素亮度。这样连抗锯齿的边缘也和原片一样。
   - 静止的元素取一帧背景干净的画面就够；闪入之类的动画逐帧提取，背景用动画结束后那一帧的闭运算结果。
3. 尊重原作者：作者签名要补回去。

实现见 [`assemble_twin_tails.py`](../projects/2026-10-24-01-neon-twin-tails/scripts/assemble_twin_tails.py) 里的 `build_overlay`。

## 对齐到原片的帧

- Kling 输出 **24 fps**。用 `fps=30` 按时间戳重采样，再按帧数裁剪或补齐（`tpad=stop=n:stop_mode=clone,trim=end_frame=n`）。
- 实测输出比原片**固定晚 1–2 帧**，没有漂移。三段里两段是 +2，一段是 +1。从开头裁掉这几帧即可（`trim=start_frame=k`）。
- **怎么量：** 不要对舞蹈片段做运动能量互相关。动作每半拍重复一次（130 BPM 时约 14 帧），相关峰会对到相邻的拍上，NEON 双马尾里测出来在 −15 到 +20 帧之间乱跳。改成：
  - 只比较**编辑不会动到的区域**，比如画面下方 40%（腿和裤子）；
  - 128×72 灰度，每帧减去均值，在 ±10 帧范围里找平均绝对差最小的偏移；
  - 每 1 秒一个窗口，取中位数，并看多少窗口落在中位数 ±1 帧以内（一致率）。
- **没有动作的镜头**（比如缓慢推镜）测不准，看硬切出现的时间：原片 2.733 秒的切点在输出里是 2.792 秒，就是 +1.75 帧。

## 取景

Kling 不严格照原片推镜，两次都偏了：第一次比原片松，第二次提示词写了 “extreme close-up”，被照字面执行，推得太紧，双马尾被切出了画面。取景要写成具体的边界，比如“结束时两个娃娃从头顶到腰都在画面里，发圈完整”，不要只写景别。背景颜色也可能被改（浅薄荷色变成暖灰），对照原片逐镜头检查。

## 验收清单

| 项 | 方法 | NEON 双马尾的结果 |
|---|---|---|
| 时长 | 数帧（`-c copy -f null` 读 `frame=`） | 690 帧 = 23.000 s |
| 音轨同步 | [`find_offset.py`](../tools/av/find_offset.py) 对原音轨 | 5 ms |
| 画面同步 | 上面的下方区域像素法，整片按窗口跑 | 舞蹈段 ±1 帧；原片段完全一致 |
| 响度 | `ebur128=peak=true`，量编码后的文件 | −14.0 LUFS / −1.0 dBTP |
| 能复现 | 用仓库里存的生成结果重新合成，比较 SHA-256 | 一致 |

## 来源

- [NEON 双马尾](../projects/2026-10-24-01-neon-twin-tails/)：Kling 4.0 Video Edit 给视频 A 的娃娃换成双马尾，五次一共 512 credits
