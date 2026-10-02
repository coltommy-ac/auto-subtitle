# auto-subtitle

中文 | [English](README.md)

这是一个适用于 macOS / Apple Silicon 的脚本工具：从本地媒体文件生成 SRT 字幕文件。

该流程使用 FFmpeg 提取单声道音频，通过
[mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
在本地转录，并将带时间戳的识别片段转换为 SRT。它还可以选择通过 DeepL 或百度翻译翻译生成的字幕。

> 这是学习/演示项目，不是面向生产环境的字幕服务。
> 请仅处理您拥有或已获授权处理的媒体文件。

## 包含内容

- `bin/autosub`：流程入口
- `bin/extract-meta` 和 `bin/extract-audio`：基于 FFmpeg/ffprobe 的媒体预处理
- `bin/stt_engine`：mlx-whisper 适配器
- `bin/make-srt.py`：带时间戳 JSON 到 SRT 的转换器
- `bin/translate.py`：可选的 DeepL/百度翻译适配器
- `samples/sample.mov`：供选择性冒烟测试使用的短演示视频
- `tests/`：用于 SRT 生成的合成、无媒体回归测试夹具

本仓库不包含训练模型、API 凭证、缓存、虚拟环境或第三方二进制文件。除 `samples/sample.mov` 外，请勿向仓库提交媒体文件。

## 环境要求

- macOS，且使用 Apple Silicon（当前 MLX 转录适配器的要求）
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/)（`brew install ffmpeg`）
- `requirements.txt` 中列出的 Python 包（由安装脚本安装）

直接运行时依赖已在 `requirements.txt` 中锁定，因此新的安装会使用同一已验证的 `mlx-whisper` CLI 版本，而非 PyPI 上最新的任意版本。

首次转录会下载所选的 Whisper 模型。默认模型为 `large`；如需快速体验，可使用较小模型，例如：

```bash
export WHISPER_MODEL=tiny
```

开始转录前，请检查前置条件：

```bash
bin/doctor
```

若使用可选翻译服务，请同时检查凭证是否可用，且不会显示其值：

```bash
bin/doctor --engine deepl
```

## 快速开始

```bash
git clone https://github.com/coltommy-ac/auto-subtitle.git
cd auto-subtitle

# 通过 Homebrew 安装 FFmpeg，创建 .venv，安装 mlx-whisper，
# 然后运行 doctor 和离线夹具测试。
scripts/setup-macos.sh

# 运行内置演示。项目会自动使用 .venv。
WHISPER_MODEL=tiny bin/autosub samples/sample.mov zh zh

# 只生成源语言字幕
WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 en en

# 生成日语字幕，并使用 DeepL 翻译为中文
WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 ja zh --engine deepl
```

Homebrew 并非 macOS 自带。若尚未安装，可从 [brew.sh](https://brew.sh) 安装后重新运行安装脚本；也可以显式允许安装脚本运行 Homebrew 官方安装程序：

```bash
scripts/setup-macos.sh --install-homebrew
```

生成的文件会放在输入媒体同一目录下，命名为 `<video-name>.<language>.srt`；工作文件会放在 `cache/` 下。

## 可选翻译凭证

在本机创建 `~/.autosub_credentials`（切勿提交）：

```ini
DEEPL_APIKEY=your_key
# 或使用百度翻译：
BAIDU_APPID=your_app_id
BAIDU_APPKEY=your_app_key
```

也可以在 shell 环境中设置相同变量。翻译请求会发送给所选服务商；转录本身在本地执行。服务商的具体配置和安全边界见 [`docs/translation-credentials.example`](docs/translation-credentials.example)。

## 验证内置夹具

```bash
tests/test_make_srt.sh
```

该测试使用合成识别结果，不会调用模型或网络。

## 可选端到端冒烟测试

冒烟测试刻意与默认夹具测试分开：它会运行 FFmpeg 和 `tiny` Whisper 模型，首次运行时可能下载该模型。该测试会创建本地媒体的五秒临时副本，并在检查后删除全部输出。

`samples/sample.mov` 是内置默认输入，只有在您显式运行下列测试时才会使用：

```bash
tests/test_smoke.sh
```

使用其他已获授权的本地文件：

```bash
tests/test_smoke.sh --media /path/to/video.mp4
```

所有可执行入口均可从任意工作目录调用；它们会通过脚本路径解析项目相对辅助程序和缓存位置。

## 限制

- 当前识别适配器仅支持 Apple Silicon。
- 准确率、延迟和模型下载大小取决于所选 Whisper 模型及源音频。
- 字幕分段逻辑有意保持简单，发布或用于专业场景前应人工检查。
- 本项目不对用户媒体提供样例或权利保证。

## 许可证

[MIT](LICENSE)。Copyright (c) 2026 guoxr。
