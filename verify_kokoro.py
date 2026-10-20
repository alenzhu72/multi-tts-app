"""Offline integration smoke test, also callable from the frozen desktop app."""
import json
import threading
import time
import wave
from pathlib import Path
from unittest.mock import patch
from audio_core import NARRATOR, export_audio, synthesize
import kokoro_local


def verify(output):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    config = dict(engine=kokoro_local.ENGINE, rate=0, timing='连续朗读',
                  kokoro_dir=str(kokoro_local.default_directory()))
    cues = [
        dict(id=1, start=0, end=3000, speaker='Alice', text='The old house was quiet. Then someone knocked at the door.'),
        dict(id=2, start=3000, end=6000, speaker='George', text='Come in, my friend. I have been expecting you.'),
    ]
    cast = {NARRATOR:dict(enabled=True, voice='af_heart'),
            'Alice':dict(enabled=True, voice='af_bella'),
            'George':dict(enabled=True, voice='bm_george')}
    began = time.perf_counter()
    used = []

    def recorded(text, voice, path, cfg, cancel):
        used.append(voice)
        synthesize(text, voice, path, cfg, cancel)

    # Model dependencies are already local; any attempted network request is a failure.
    with patch('urllib.request.urlopen', side_effect=AssertionError('Offline test attempted network')):
        for suffix in ('wav', 'mp3'):
            export_audio(cues, cast, config, root / ('dialogue.' + suffix),
                         threading.Event(), lambda _: None, recorded)
        config['single_narrator'] = True
        export_audio(cues, cast, config, root/'narrator.wav',
                     threading.Event(), lambda _: None, recorded)
    assert used == ['af_bella', 'bm_george'] * 2 + ['af_heart'] * 2, used
    with wave.open(str(root/'dialogue.wav')) as audio:
        duration = audio.getnframes() / audio.getframerate()
        assert duration > 1
        assert any(audio.readframes(audio.getnframes()))
    assert (root/'dialogue.mp3').stat().st_size > 1000
    result = dict(elapsed_seconds=round(time.perf_counter()-began, 2),
                  dialogue_seconds=round(duration, 2), voices=used,
                  provider=kokoro_local._model.sess.get_providers())
    (root/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    print(verify('verification/kokoro'))
