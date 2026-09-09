import tempfile
import unittest
from pathlib import Path
from text_srt import duration_ms, text_to_cues, to_srt, read_text
from audio_core import parse_srt, NARRATOR


class TextSubtitleTests(unittest.TestCase):
    def test_duration_formats_and_invalid(self):
        self.assertIsNone(duration_ms(' '))
        self.assertEqual(duration_ms('90.125'),90125)
        self.assertEqual(duration_ms('01:30.125'),90125)
        self.assertEqual(duration_ms('01:01:30'),3690000)
        for value in ('0','-1','NaN','inf','1:60','abc','0.0001'):
            with self.subTest(value=value), self.assertRaises(ValueError): duration_ms(value)

    def test_explicit_length_exact_and_proportional(self):
        cues = text_to_cues('你好。\n这是一个比较长的句子，需要更多时间。','01:30.125')
        self.assertEqual(cues[0]['start'],0)
        self.assertEqual(cues[-1]['end'],90125)
        self.assertEqual(cues[0]['end'],cues[1]['start'])
        self.assertGreater(cues[1]['end']-cues[1]['start'],cues[0]['end'])

    def test_auto_and_speaker_retention_roundtrip(self):
        cues = text_to_cues('林晓：你好！再见。\nJohn: Hello world. Goodbye!\n旁白在这里。')
        self.assertEqual([c['speaker'] for c in cues],['林晓','林晓','John','John',NARRATOR])
        self.assertTrue(all(c['end']>c['start'] for c in cues))
        parsed = parse_srt(to_srt(cues,True))
        self.assertEqual(parsed,cues)
        self.assertNotIn('[John]',to_srt(cues))

    def test_long_text_and_decimal_not_lost(self):
        text = '价格是 3.14 元。'+'很'*260
        cues = text_to_cues(text)
        self.assertEqual(''.join(c['text'] for c in cues),text)
        self.assertTrue(all(len(c['text'])<=100 for c in cues))

    def test_blank_and_too_short(self):
        with self.assertRaises(ValueError): text_to_cues('  \n')
        with self.assertRaises(ValueError): text_to_cues('一。二。','0.001')

    def test_encodings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.txt'
            for encoding in ('utf-8-sig','utf-16','gb18030'):
                path.write_bytes('你好。Hello.'.encode(encoding))
                self.assertEqual(read_text(path),'你好。Hello.')


if __name__ == '__main__': unittest.main()
