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
        cues = text_to_cues('林晓：你好！再见。\nJohn: Hello world. Goodbye!\n旁白在这里。',detect_speakers=True)
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

    def test_standalone_labels_no_longer_fail(self):
        for line in ('[Music]', '[Chapter 3]', 'Adrian:', '注意：'):
            for detect in (False, True):
                with self.subTest(line=line, detect=detect):
                    cues = text_to_cues(line,detect_speakers=detect)
                    self.assertEqual(cues[0]['text'],line)
                    self.assertEqual(parse_srt(to_srt(cues))[0]['text'],line)

    def test_story_headings_and_notices_preserved(self):
        source = 'FLOATING HEADS OF FORT SOLOSO\n\nCHAPTER 3 OF SENTOSA AFTER DARK\nCaution Notice: Extreme Supernatural Horror\n[Music]\nAdrian:\nThe island remembers.'
        cues = text_to_cues(source,'60')
        self.assertEqual([c['text'] for c in cues],[line for line in source.splitlines() if line])
        self.assertTrue(all(c['speaker']==NARRATOR for c in cues))
        self.assertEqual(cues[-1]['end'],60000)
        self.assertIn('Caution Notice:',to_srt(cues))

    def test_encodings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.txt'
            for encoding in ('utf-8-sig','utf-16','gb18030'):
                path.write_bytes('你好。Hello.'.encode(encoding))
                self.assertEqual(read_text(path),'你好。Hello.')


if __name__ == '__main__': unittest.main()
