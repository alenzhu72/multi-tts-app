# v1.0.6 — 单一画外音 / Single narrator

- 默认单一画外音模式：导入 TXT / SRT，选择画外音，直接导出 WAV / MP3，无需 AI 人物识别或 AI 密钥。
- 单一模式覆盖全部人物的实际配音，保留原有角色和声音设置，随时切回多角色。
- 字幕试听、实际声音显示和音频导出遵循相同模式。
- 工程保存配音模式，旧工程兼容；AI 识别成功后切回多角色。
- Windows 单文件 EXE，内置 Python 和 FFmpeg；Edge TTS 需要网络。

使用：下载 SRT-Voice-Studio.exe，打开后导入文字，在「人物与声音」选择画外音，然后导出 MP3 / WAV。

验证：21 项自动化测试通过；实际 Edge TTS 中文 WAV / MP3 导出成功；打包 EXE 启动测试通过。EXE 为 Windows x64 未签名构建。
