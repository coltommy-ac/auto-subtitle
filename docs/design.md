# auto-subtitle 详细设计文档

> 版本：v2.0 · 更新日期：2026-10-02 · 本文以当前工作区的受维护入口和测试为准。

## 1. 项目边界

**auto-subtitle** 是一个面向 macOS / Apple Silicon 的本地媒体字幕生成演示项目。它从用户已获授权的本地媒体提取音频，使用本地 `mlx-whisper` 转录，生成 SRT；当源语言和目标语言不同时，可调用 DeepL 或百度翻译翻译字幕文本。

项目不提供在线服务、队列、账号体系或生产级质量保证。转录在本机运行；只有启用翻译时，字幕文本才会被发送到所选翻译服务商。

### 1.1 支持的语言代码

| 代码 | 语言 | 用途 |
|---|---|---|
| `en` | 英语 | 转录与翻译 |
| `ja` | 日语 | 转录与翻译 |
| `es` | 西班牙语 | 转录与翻译 |
| `ar` | 阿拉伯语 | 转录与翻译 |
| `zh` | 中文 | 转录与翻译；默认目标语言 |

实际转录语言由 `mlx_whisper --language` 接收；未在上表内的值会原样传入该 CLI。翻译适配器对 DeepL 的上述代码有显式映射。

### 1.2 运行前提

- macOS，Apple Silicon（`arm64`）
- Python 3.10+
- FFmpeg / ffprobe
- `mlx-whisper==0.4.3`（项目 `.venv` 或当前 `PATH`）
- 可选：DeepL 的 `DEEPL_APIKEY`，或百度翻译的 `BAIDU_APPID`、`BAIDU_APPKEY`

`scripts/setup-macos.sh` 会安装缺失的 FFmpeg 与 Python、创建 `.venv`、安装 Python 依赖，并运行离线夹具测试；默认不会下载 Whisper 模型或创建凭证。`bin/doctor` 只检查依赖与凭证是否存在，不会显示密钥内容、安装软件或下载模型。

## 2. 总体架构

```
受授权本地媒体 / 已有 cache 目录
              │
              ├── 媒体文件
              │     │
              │     ▼
              │  extract-meta（ffprobe） ──> meta
              │     │
              │     ▼
              │  extract-audio（ffmpeg） ─> index + clip_<offset>.flac
              │
              ▼
speech2text ──> stt_engine（mlx_whisper） ─> clip_<offset>.<lang>.txt
              │
              ▼
make-srt.py ──> output.<source-lang>.srt
              │
              ├── 源语言 = 目标语言 ──> 复制到媒体同目录
              │
              └── 源语言 ≠ 目标语言
                    ▼
              translate.py（DeepL / 百度 HTTPS） ─> output.<target-lang>.srt
                    ▼
              复制到媒体同目录
```

`bin/autosub` 是编排入口。若输入是缓存目录，则跳过元数据和音频提取，从已有 `index` 与音频片段继续执行；此模式不复制最终字幕到媒体目录。

## 3. 调用接口与执行流程

### 3.1 主入口：`bin/autosub`

```bash
bin/autosub <video-filename|cache-dir> <original-lang> [subtitle-lang] \
  [--clean] [--limit <minutes>] [--engine deepl|baidu]
```

- 目标语言默认 `zh`，翻译引擎默认 `deepl`。
- 输入为媒体文件时，缓存目录为 `<项目根目录>/cache/<媒体文件名去扩展名>`。
- `--clean` 仅在输入为媒体文件时删除该媒体名对应的缓存后重新提取；这是不可恢复的缓存清理操作。
- `--limit N` 仅处理前 `N` 分钟，用于试跑。
- 先生成 `output.<original-lang>.srt`；源、目标语言不同才调用翻译器。
- 成功后将目标 SRT 复制到输入媒体同目录，命名为 `<媒体名>.<目标语言>.srt`。

### 3.2 元数据：`bin/extract-meta`

接口：`bin/extract-meta <media-file> <cache-dir>`。

脚本调用 `ffprobe -show_format -show_streams`，以嵌入式 Python 解析 JSON，并将可用字段写入 `<cache-dir>/meta`：

| 字段 | 来源 / 含义 |
|---|---|
| `ID_LENGTH` | 容器时长，秒（向下取整） |
| `ID_AUDIO_ID`、`ID_AUDIO_CODEC` | 音频流的索引、编码名 |
| `ID_AUDIO_RATE`、`ID_AUDIO_BITRATE`、`ID_AUDIO_NCH` | 音频采样率、比特率、声道数 |
| `ID_VIDEO_ID`、`ID_VIDEO_CODEC` | 视频流索引、编码名 |
| `ID_VIDEO_WIDTH`、`ID_VIDEO_HEIGHT`、`ID_VIDEO_FPS`、`ID_VIDEO_BITRATE` | 视频尺寸、帧率、比特率 |

`extract-audio` 依赖音频采样率、比特率、声道数与时长；这些字段缺失会使流程停止。

### 3.3 音频切片：`bin/extract-audio`

接口：`bin/extract-audio <media-file> <cache-dir> [limit-minutes]`。

1. 调用 `extract-meta` 更新 `meta`。
2. 将输出重采样为 **16 kHz、单声道 FLAC**，并使用 FFmpeg 的 `loudnorm` 滤镜。
3. 以 **30 秒**为固定步长生成 `clip_<offset>.flac`，直至媒体结尾或 `--limit` 截止；不存在一小时上限。
4. 每个片段先写入 `.tmp`，非空后再原子重命名，并把起始秒写入 `index`。
5. 若已有非空 `index`，从其中最大偏移的下一段继续切片，避免重复生成已记录的尾部片段。

`index` 是下游的唯一片段清单：每行一个以秒为单位的整数偏移。

### 3.4 转录：`bin/speech2text` 与 `bin/stt_engine`

`speech2text` 按 `index` 顺序读取片段，为每个 `clip_<offset>.flac` 生成 `clip_<offset>.<lang>.txt`。已有同语言文本文件时会跳过，因此支持在中断后继续转录；可选第三参数指定需要跳过的起始偏移。

`stt_engine` 的接口为：

```bash
bin/stt_engine -s <audio.flac> -t <output.txt> -l <language>
```

它优先使用项目 `.venv/bin/mlx_whisper`，其次使用 `PATH` 中的 `mlx_whisper`。模型由 `WHISPER_MODEL` 控制，默认 `large`，实际传入的模型名为 `mlx-community/whisper-<model>-mlx`。首次使用某模型会下载模型文件。

`mlx_whisper` 先在片段目录输出原始 `<clip>.json`。适配器随后将其 `segments` 转为本项目稳定的 JSON 契约，临时文件写入成功后原子替换为目标 `.txt`，再删除原始 JSON：

```json
{
  "results": [
    {
      "alternatives": [
        {
          "transcript": "hello world",
          "timestamps": [["<s>", 0.5, 0.5], ["<e>", 1.6, 1.6]]
        }
      ]
    }
  ]
}
```

时间戳相对于当前音频片段；`make-srt.py` 会加上 `index` 中的片段偏移。

### 3.5 SRT 生成：`bin/make-srt.py`

接口：

```bash
python3 bin/make-srt.py -d <cache-dir> -l <language>
python3 bin/make-srt.py -f <single-stt-json>
```

目录模式按照 `index` 合并所有 `clip_<offset>.<language>.txt`；单文件模式生成同名 `.srt`。它选择每个 `result` 的第一条 `alternative`，用首、末时间戳确定字幕区间，并使用三位毫秒的标准 `HH:MM:SS,mmm` 格式。

相邻字幕的间隔小于 `0.5` 秒且合并后时长不超过 `5.0` 秒时，会合并为一条。单个文本文件缺失或 JSON 不合法时会记录 warning 并继续；若没有任何有效字幕，命令失败。目录模式用 `output.<lang>.srt.tmp` 完成写入后原子替换正式文件。

### 3.6 翻译：`bin/translate.py`

接口：

```bash
python3 bin/translate.py -i <input.srt> -o <output.srt> \
  -s <source-lang> -t <target-lang> [--engine deepl|baidu]
```

凭证从 `~/.autosub_credentials` 读取，环境变量仅在该文件没有对应键时作为回退；不应将凭证加入仓库。样例和权限建议见 `docs/translation-credentials.example`。

| 引擎 | 网络端点与鉴权 | 批处理 / 失败语义 |
|---|---|---|
| DeepL | `https://api-free.deepl.com/v2/translate`；`Authorization: DeepL-Auth-Key` | 每批 20 条；批次失败时保留原文，并以退出码 3 结束 |
| 百度翻译 | `https://api.fanyi.baidu.com/api/trans/vip/translate`；MD5 签名 | 每批 20 条、条目以换行连接；批次间等待 1 秒，失败时保留原文，并以退出码 3 结束 |

翻译器只改写每条 SRT 的文本，保留序号和时间轴。输出先写到 `<output>.tmp`，完成后再原子替换目标文件。

## 4. 文件布局与数据生命周期

```text
auto-subtitle/
├── bin/                         # 受维护的可执行入口
│   ├── autosub                  # 流程编排
│   ├── doctor                   # 前置条件与凭证存在性检查
│   ├── extract-meta             # ffprobe 元数据适配器
│   ├── extract-audio            # ffmpeg 音频切片器
│   ├── speech2text              # 片段转录循环
│   ├── stt_engine               # mlx-whisper 适配器
│   ├── make-srt.py              # JSON 到 SRT
│   └── translate.py             # DeepL / 百度翻译
├── scripts/setup-macos.sh       # macOS 本地安装与离线验证
├── tests/                       # 离线 SRT 夹具与可选端到端冒烟测试
├── docs/translation-credentials.example
├── requirements.txt             # mlx-whisper 精确版本
├── samples/sample.mov           # 仅供显式冒烟测试的短媒体
└── cache/<media-base-name>/     # 未跟踪的运行时工作目录
    ├── meta
    ├── index
    ├── clip_<offset>.flac
    ├── clip_<offset>.<lang>.txt
    └── output.<lang>.srt
```

`.gitignore` 排除了 `cache/`、`.venv/`、运行时字幕、凭证、旧版工具目录、PHP 实现与备份文件。它们可能存在于本地工作区，但不属于当前受维护实现。

## 5. 验证策略

| 检查 | 命令 | 覆盖范围 | 网络 / 模型 |
|---|---|---|---|
| 前置条件 | `bin/doctor` | 平台、Python、FFmpeg、mlx-whisper | 否 |
| 翻译凭证存在性 | `bin/doctor --engine deepl` 或 `baidu` | 所选凭证名称，不打印值 | 否 |
| 离线回归 | `tests/test_make_srt.sh` | 合成 JSON 到预期 SRT 的逐字节差异 | 否 |
| 端到端冒烟 | `tests/test_smoke.sh [--media path]` | FFmpeg、tiny 模型、完整编排和非空 SRT | 可能下载模型；不调用翻译 |

当前已通过的最低回归基线是 `tests/test_make_srt.sh`。冒烟测试刻意不作为安装脚本的默认网络验证：它会复制前五秒授权本地媒体到临时目录，并在结束时清理临时媒体与对应缓存。

## 6. 当前限制与工程风险

- 转录适配器限定 macOS Apple Silicon；其他平台没有兼容后端。
- 默认 `large` 模型的首次下载、存储占用和运行时延取决于模型与媒体，快速试跑宜显式设置 `WHISPER_MODEL=tiny`。
- 缓存目录仅以媒体文件基名命名；不同目录中的同名媒体会共享缓存。并发处理同名文件或复用旧缓存前，应使用 `--clean` 或直接传入明确的缓存目录。
- 续切只依据 `index` 的最大偏移，不检查历史片段是否缺失或损坏；转录续跑同样只根据目标 `.txt` 是否存在判断完成。
- SRT 解析按空行和三行头部处理；多行字幕文本或异常 SRT 格式没有专门的保真解析器。
- 翻译批次失败会保留原文并返回非零状态，避免静默把部分翻译当作完全成功；重新运行会重译整个输出，而非按条目断点续传。
- 字幕分段仅按时间间隔和最长时长合并，未按阅读速度、字符数、标点或说话人进行优化，发布前应人工复核。
- `bin/identify`、`*.php` 与 `*.bak` 是未跟踪的旧本地材料，不应作为当前行为依据。

## 7. 历史迁移说明

v1 文档中描述的 MPlayer/MEncoder、IBM Watson 二进制、PHP 生成/翻译、HTTP 翻译端点、硬编码 API 密钥、60 秒切片和一小时截断均不是当前受维护链路。当前实现使用 FFmpeg/ffprobe、MLX Whisper、Python、HTTPS、外置凭证、30 秒切片，并已实现进度显示、字幕合并、原子输出、缓存续跑和最终字幕复制。
