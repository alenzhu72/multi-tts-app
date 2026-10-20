import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import kokoro_local as k


class KokoroTests(unittest.TestCase):
    def test_voice_labels_and_invalid_voice(self):
        self.assertEqual(len(k.voice_choices()), 28)
        self.assertEqual(k.voice_id(k.voice_label('bm_george')), 'bm_george')
        self.assertTrue(all('女声' in s for s in k.voice_choices('女声')))
        with self.assertRaises(ValueError): k.voice_id('en-US-AriaNeural')

    def test_float_speed_preserves_fraction(self):
        raw = MagicMock()
        adapter = k._FloatSpeedSession(raw)
        adapter.speed = 1.25
        adapter.run(None, {'speed':np.array([1],dtype=np.int32)})
        speed = raw.run.call_args.args[1]['speed']
        self.assertEqual(speed.dtype, np.float32)
        self.assertEqual(speed[0], 1.25)

    def test_incomplete_download_does_not_install(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {'Content-Length':'10'}
        response.read.side_effect = [b'abc', b'']
        with tempfile.TemporaryDirectory() as folder:
            with patch('urllib.request.urlopen', return_value=response):
                with self.assertRaises(RuntimeError):
                    k.download(folder, threading.Event(), lambda _:None)
            self.assertFalse(list(Path(folder).iterdir()))

    def test_missing_models_and_cancel_do_not_load_model(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Kokoro'):
                k.check_files(folder)
            cancel = threading.Event()
            cancel.set()
            with patch('urllib.request.urlopen') as request:
                with self.assertRaises(InterruptedError):
                    k.download(folder, cancel, lambda _:None)
                request.assert_not_called()
