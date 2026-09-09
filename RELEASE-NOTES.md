# v1.0.1 · TXT 转 SRT 修复 / TXT import fix

- 修复 TXT 包含单独的 `[Music]`、`Adrian:` 等内容时提示“没有可朗读文本”的问题。
- TXT 默认完整保留标题、冒号前缀和方括号内容；人物名前缀提取改为可选。
- Fix conversion failures on standalone bracketed text or colon labels. Preserve prose by default; speaker-prefix extraction is now optional.
- 13 项自动测试通过 / 13 automated tests passed.

## v1.0.0 功能 / Features

Windows 桌面多角色配音工具，支持中英文界面。

- 导入 SRT，或粘贴文字 / 导入 TXT 自动分句生成 SRT。
- 设置字幕总时长，或留空按阅读速度估算；支持导出 SRT。
- AI 故事人物识别，手动添加人物、逐句修改及批量分配。
- 选定人物独立声音，其他人物统一使用画外音。
- Edge TTS 和兼容 TTS API；试听及整段 MP3 / WAV 导出。
- 保存和恢复工程，API 密钥不写入工程文件。

下载 `SRT-Voice-Studio.exe` 后双击运行，无需安装 Python 或 FFmpeg。Edge TTS 需要联网；AI 识别需填写接口地址、模型及凭据。AI 与兼容 TTS 付费接口尚未进行真实调用验证。

总时长设置控制字幕时间轴，不强制压缩配音音频。本版本为未签名的 Windows x64 构建。

English: Import SRT or convert TXT/pasted text into subtitles with optional total duration. Identify and edit characters, assign individual voices or a shared narrator, and export MP3/WAV. Bilingual Chinese/English UI. No Python installation required. Edge TTS needs internet access; AI identification requires a configured API endpoint and credentials.

Validation: 11 automated tests passed; TXT-to-SRT UI export and packaged EXE startup verified. Real Edge TTS multi-voice MP3 generation verified.
