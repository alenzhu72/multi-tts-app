"""Offline English Kokoro adapter. Model files live beside the app, not in the EXE."""
from pathlib import Path
import sys
import threading
import urllib.request

ENGINE = 'Kokoro 本地 / Local'
DEFAULT_VOICE = 'af_heart'
VOICE_IDS = (
    'af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova '
    'af_river af_sarah af_sky am_adam am_echo am_eric am_fenrir am_liam '
    'am_michael am_onyx am_puck am_santa bf_alice bf_emma bf_isabella bf_lily '
    'bm_daniel bm_fable bm_george bm_lewis'
).split()
MODEL_FILES = ('kokoro-v1.0.onnx', 'voices-v1.0.bin')
DOWNLOAD_BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
_lock = threading.Lock()
_model = None
_model_key = None


class _FloatSpeedSession:
    """0.4.7 assumes integer speed for input_ids exports; v1.0 requires float."""
    def __init__(self, session):
        self.session = session
        self.speed = 1.0

    def __getattr__(self, name):
        return getattr(self.session, name)

    def run(self, outputs, inputs):
        import numpy as np
        inputs = dict(inputs)
        inputs['speed'] = np.array([self.speed], dtype=np.float32)
        return self.session.run(outputs, inputs)


def default_directory():
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    return root / 'models' / 'kokoro'


def voice_id(value):
    ident = value.split(' · ')[0].strip()
    if ident not in VOICE_IDS:
        raise ValueError('请选择 Kokoro 英语声音 / Select a Kokoro English voice.')
    return ident


def voice_label(ident):
    region = '美式' if ident[0] == 'a' else '英式'
    gender = '女声' if ident[1] == 'f' else '男声'
    return f'{ident} · {region}{gender}'


def voice_choices(search=''):
    return [voice_label(v) for v in VOICE_IDS if search.lower() in voice_label(v).lower()]


def paths(directory):
    root = Path(directory) if directory else default_directory()
    return [root / name for name in MODEL_FILES]


def check_files(directory):
    files = paths(directory)
    if any(not p.is_file() or p.stat().st_size == 0 for p in files):
        raise ValueError('Kokoro 模型未安装。点击“下载 Kokoro 模型”，或选择含模型的文件夹。 / Download Kokoro models or select their folder.')
    return files


def download(directory, cancel, progress):
    for target in paths(directory):
        if cancel.is_set():
            raise InterruptedError('已取消 / Cancelled')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size:
            continue
        partial = target.with_suffix(target.suffix + '.part')
        try:
            with urllib.request.urlopen(DOWNLOAD_BASE + target.name, timeout=30) as response, partial.open('wb') as output:
                total = int(response.headers.get('Content-Length', 0))
                count = 0
                while True:
                    if cancel.is_set():
                        raise InterruptedError('已取消 / Cancelled')
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    count += len(chunk)
                    progress(f'下载 {target.name}: {count // 1048576} / {total // 1048576} MB')
                if not count or (total and count != total):
                    raise RuntimeError('模型下载不完整，请重试 / Incomplete model download; retry.')
            if cancel.is_set():
                raise InterruptedError('已取消 / Cancelled')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    return str(paths(directory)[0].parent)


def save_wav(text, voice, output, config, cancel):
    global _model, _model_key
    ident = voice_id(voice)
    files = check_files(config.get('kokoro_dir'))
    key = tuple((str(p.resolve()), p.stat().st_mtime_ns) for p in files)
    with _lock:
        if cancel.is_set():
            raise InterruptedError('已取消 / Cancelled')
        import soundfile as sf
        if _model is None or key != _model_key:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            # Leave CPU capacity for the desktop UI; CPU provider needs no CUDA.
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            _model = None
            session = ort.InferenceSession(str(files[0]), sess_options=options, providers=['CPUExecutionProvider'])
            _model = Kokoro.from_session(session, str(files[1]))
            _model.sess = _FloatSpeedSession(session)
            _model_key = key
        speed = max(.5, min(2, 1 + config['rate'] / 100))
        _model.sess.speed = speed
        samples, rate = _model.create(
            text, voice=ident, speed=speed,
            lang='en-us' if ident.startswith('a') else 'en-gb')
        if cancel.is_set():
            raise InterruptedError('已取消 / Cancelled')
        if not len(samples):
            raise ValueError('Kokoro 未生成音频 / Kokoro returned empty audio.')
        sf.write(str(output), samples, rate, format='WAV', subtype='PCM_16')
