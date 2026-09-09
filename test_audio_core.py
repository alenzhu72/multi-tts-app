import json
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from audio_core import *

SRT = '\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\n林晓：你好\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\n门开了。'

class PipelineTests(unittest.TestCase):
    def test_parser_and_unknown(self):
        cues = parse_srt(SRT)
        self.assertEqual((cues[0]['speaker'],cues[0]['text']),('林晓','你好'))
        self.assertEqual(cues[1]['speaker'],NARRATOR)
        self.assertEqual(cues[1]['start'],3000)
        with self.assertRaises(ValueError): parse_srt('1\n00:00:01,000 --> 00:00:00,000\nx')
        with self.assertRaises(ValueError): parse_srt(SRT+'\n\ninvalid block')

    def test_unselected_falls_back(self):
        cast = {NARRATOR:dict(enabled=True,voice='n'),'A':dict(enabled=True,voice='a'),'B':dict(enabled=False,voice='b')}
        self.assertEqual(effective_voice('A',cast),'a')
        self.assertEqual(effective_voice('B',cast),'n')
        self.assertEqual(effective_voice('missing',cast),'n')

    def test_ai_missing_duplicate_and_unknown_ids_rejected(self):
        cues = parse_srt(SRT)
        for items in [[{'id':1,'speaker':'A'}],[{'id':1,'speaker':'A'},{'id':1,'speaker':'B'}],[{'id':1,'speaker':'A'},{'id':3,'speaker':'B'}]]:
            with self.assertRaises(ValueError): validate_assignments({'assignments':items},cues)

    def test_ai_integration_contract(self):
        content = json.dumps({'assignments':[{'id':1,'speaker':'林晓'},{'id':2,'speaker':NARRATOR}]})
        response = json.dumps({'choices':[{'message':{'content':content}}]}).encode()
        with patch('audio_core.post_json',return_value=response):
            self.assertEqual(recognize(parse_srt(SRT),dict(base='http://localhost',key='',model='test'),threading.Event(),lambda _:None),{1:'林晓',2:NARRATOR})

    def test_real_conversion_and_timing(self):
        used = []
        def fake(text,voice,path,config,cancel):
            used.append(voice)
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,24000,0,'NONE','not compressed')); f.writeframes(b'\x01\x00'*2400)
        with tempfile.TemporaryDirectory() as folder:
            cast = {NARRATOR:dict(enabled=True,voice='n'),'林晓':dict(enabled=False,voice='x')}
            output = Path(folder)/'test.wav'
            export_audio(parse_srt(SRT),cast,dict(timing='按字幕起点（超长顺延）'),output,threading.Event(),lambda _:None,fake)
            with wave.open(str(output),'rb') as f: self.assertEqual(f.getnframes(),74400)
            self.assertEqual(used,['n','n'])
            mp3 = Path(folder)/'test.mp3'
            export_audio(parse_srt(SRT),cast,dict(timing='连续朗读'),mp3,threading.Event(),lambda _:None,fake)
            self.assertGreater(mp3.stat().st_size,100)
            cancel = threading.Event(); cancel.set()
            original = output.read_bytes()
            with self.assertRaises(InterruptedError): export_audio(parse_srt(SRT),cast,{},output,cancel,lambda _:None,fake)
            self.assertEqual(output.read_bytes(),original)

    def test_minimax_reasoning_and_request(self):
        assignments = {'assignments':[{'id':1,'speaker':'林晓'},{'id':2,'speaker':NARRATOR}]}
        for prefix in ('', '<think>internal reasoning\nnot JSON</think>\n'):
            response = json.dumps({'choices':[{'finish_reason':'stop','message':{'content':prefix+'```json\n'+json.dumps(assignments)+'\n```','reasoning_details':[{'text':'reasoning'}]}}]}).encode()
            with patch('audio_core.post_json',return_value=response) as call:
                result = recognize(parse_srt(SRT),dict(base=MINIMAX_BASE,key='test-only',model=MINIMAX_MODEL),threading.Event(),lambda _:None)
                self.assertEqual(result,{1:'林晓',2:NARRATOR})
                args = call.call_args.args
                self.assertEqual(args[:2],(MINIMAX_BASE,'/chat/completions'))
                self.assertTrue(args[3]['reasoning_split'])
                self.assertEqual(args[3]['model'],MINIMAX_MODEL)

    def test_truncated_or_missing_ai_response(self):
        for response in ({'choices':[]},{'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}, {'choices':[{'message':{'content':None}}]}, {'base_resp':{'status_code':1004}}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                ai_response_json(json.dumps(response).encode())

if __name__ == '__main__': unittest.main()
