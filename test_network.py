import io
import threading
import unittest
import urllib.error
from unittest.mock import MagicMock, patch
from audio_core import post_json

class RequestTests(unittest.TestCase):
    def setUp(self):
        self.cancel = MagicMock()
        self.cancel.is_set.return_value = False
        self.cancel.wait.return_value = False
        self.response = MagicMock()
        self.response.__enter__.return_value.read.return_value = b'ok'

    def call(self, **kwargs):
        return post_json('https://example.test/v1','/chat/completions','test',{},cancel=self.cancel,**kwargs)

    def test_read_timeout_retries_and_recovers(self):
        failed = MagicMock()
        failed.__enter__.return_value.read.side_effect = TimeoutError('The read operation timed out')
        updates = []
        with patch('audio_core.urllib.request.urlopen',side_effect=[failed,self.response]) as request:
            self.assertEqual(self.call(progress=updates.append,timeout=300),b'ok')
            self.assertEqual(request.call_count,2)
            self.assertEqual(request.call_args.kwargs['timeout'],300)
        self.assertIn('2/3',updates[0])

    def test_failure_is_bounded_and_identifies_operation(self):
        with patch('audio_core.urllib.request.urlopen',side_effect=TimeoutError()) as request:
            with self.assertRaisesRegex(RuntimeError,'AI test.*3'):
                self.call(label='AI test')
            self.assertEqual(request.call_count,3)

    def test_authentication_error_not_retried(self):
        error = urllib.error.HTTPError('https://example.test',401,'Unauthorized',{},io.BytesIO())
        with patch('audio_core.urllib.request.urlopen',side_effect=error) as request:
            with self.assertRaisesRegex(RuntimeError,'401'): self.call()
            self.assertEqual(request.call_count,1)

    def test_transient_http_error_retried(self):
        error = urllib.error.HTTPError('https://example.test',503,'Unavailable',{},io.BytesIO())
        with patch('audio_core.urllib.request.urlopen',side_effect=[error,self.response]):
            self.assertEqual(self.call(),b'ok')

    def test_cancel_during_backoff_stops_retry(self):
        self.cancel.wait.return_value = True
        with patch('audio_core.urllib.request.urlopen',side_effect=TimeoutError()) as request:
            with self.assertRaises(InterruptedError): self.call()
            self.assertEqual(request.call_count,1)

    def test_cancel_before_request(self):
        self.cancel.is_set.return_value = True
        with patch('audio_core.urllib.request.urlopen') as request:
            with self.assertRaises(InterruptedError): self.call()
            request.assert_not_called()

if __name__ == '__main__': unittest.main()
