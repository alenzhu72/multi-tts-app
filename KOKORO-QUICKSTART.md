# Kokoro 本地配音

1. 解压整个文件夹，保留 `SRT-Voice-Studio.exe` 旁边的 `models/kokoro`。
2. 打开 EXE，引擎选择 **Kokoro 本地 / Local**。
3. 导入 TXT/SRT。单一画外音可直接选声音；多角色模式下为各角色勾选独立配音、选择声音。
4. 在“人物与声音”中点“试听”。af/am = 美式女/男，bf/bm = 英式女/男。
5. 导出 MP3 或 WAV。可调整语速，也可保存工程。

本次接入仅支持英语。完全在 CPU 上运行，无需 API Key、网络或显卡。
AI 人物识别仍需原有 AI 服务；也可手动添加角色并批量分配字幕。
首次打开尚无模型时，可点击下载按钮；模型目录也可手动选择。
取消在当前句合成结束后生效；不要只移动 EXE 而遗漏模型文件夹。

原始模型：https://huggingface.co/hexgrad/Kokoro-82M
ONNX 模型与声音：https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1
声音身份为预设，不保证年龄或性格，也不支持用录音克隆声音。

## 第三方组件

Kokoro 模型使用 Apache-2.0；具体声音许可及来源见原始模型的 VOICES.md。
Kokoro ONNX 运行库：https://github.com/thewh1teagle/kokoro-onnx
ONNX Runtime：https://github.com/microsoft/onnxruntime
Phonemizer：https://github.com/bootphon/phonemizer （GPL）
eSpeak NG：https://github.com/espeak-ng/espeak-ng （GPL）
eSpeak NG loader：https://github.com/thewh1teagle/espeakng-loader
SoundFile：https://github.com/bastibe/python-soundfile

打包第三方库的原始许可文件见 LICENSES 文件夹；各组件遵循各自许可。
