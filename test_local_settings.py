import tempfile
import unittest
from pathlib import Path
from local_settings import save_settings, load_settings, clear_settings

class LocalSettingsTests(unittest.TestCase):
    def test_encrypted_roundtrip_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.dpapi'
            self.assertEqual(load_settings(path), {})
            data = {'key':'fake-test-key-123', 'base':'https://api.minimax.cn/v1', 'model':'MiniMax-M2.7'}
            save_settings(data,path)
            self.assertNotIn(b'fake-test-key-123', path.read_bytes())
            self.assertEqual(load_settings(path)['key'], data['key'])
            self.assertEqual(load_settings(path)['base'], data['base'])
            save_settings({**data,'key':'replacement-test-key'},path)
            self.assertEqual(load_settings(path)['key'],'replacement-test-key')
            clear_settings(path)
            self.assertEqual(load_settings(path), {})

    def test_corrupt_file_is_not_used(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.dpapi'
            path.write_bytes(b'not an encrypted credential')
            with self.assertRaises(OSError): load_settings(path)

if __name__ == '__main__': unittest.main()
