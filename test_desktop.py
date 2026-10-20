import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from desktop import App
from audio_core import NARRATOR

class DesktopModeTests(unittest.TestCase):
    def test_kokoro_preview_extension_and_project(self):
        import kokoro_local as k
        with patch('desktop.load_settings',return_value={}):
            app = App()
        app.withdraw()
        self.addCleanup(app.destroy)
        self.addCleanup(app.preview_dir.cleanup)
        app.vars['engine'].set(k.ENGINE)
        app.change_engine()
        self.assertEqual(app.cast[NARRATOR]['voice'],k.voice_label('af_heart'))
        self.assertEqual(str(app.language_menu['state']), 'disabled')
        with tempfile.TemporaryDirectory() as folder:
            for name in k.MODEL_FILES:
                (Path(folder)/name).write_bytes(b'test')
            app.vars['kokoro_dir'].set(folder)
            with patch('desktop.synthesize') as synth, patch.object(app,'run',side_effect=lambda work,done:work()):
                app.preview('Hello',k.voice_label('am_michael'))
                self.assertEqual(synth.call_args.args[2].suffix,'.wav')
                self.assertEqual(synth.call_args.args[3]['engine'], k.ENGINE)
            project = str(Path(folder)/'project.json')
            with patch('desktop.filedialog.asksaveasfilename',return_value=project):
                app.save_project()
            app.vars['engine'].set('Edge TTS')
            with patch('desktop.filedialog.askopenfilename',return_value=project):
                app.load_project()
            self.assertEqual(app.vars['engine'].get(),k.ENGINE)
            self.assertEqual(app.vars['kokoro_dir'].get(),folder)

    def test_mode_preview_export_and_project_roundtrip(self):
        with patch('desktop.load_settings',return_value={}):
            app = App()
        app.withdraw()
        self.addCleanup(app.destroy)
        app.cues = [dict(id=1,start=0,end=1000,text='Hello',speaker='Alice')]
        app.cast = {NARRATOR:dict(enabled=True,voice='en-US-AriaNeural'), 'Alice':dict(enabled=True,voice='en-US-GuyNeural')}
        app.render()
        app.tree.selection_set('0')
        self.assertTrue(app.config()['single_narrator'])
        self.assertEqual(app.tree.set('0','voice'),'en-US-AriaNeural')
        with patch.object(app,'preview') as preview:
            app.preview_line()
            preview.assert_called_once_with('Hello','en-US-AriaNeural')
        with tempfile.TemporaryDirectory() as folder:
            project = str(Path(folder)/'project.json')
            with patch('desktop.filedialog.asksaveasfilename',return_value=project): app.save_project()
            app.vars['voice_mode'].set('多角色 / Multiple voices')
            app.render()
            self.assertEqual(app.tree.set('0','voice'),'en-US-GuyNeural')
            with patch('desktop.filedialog.askopenfilename',return_value=project): app.load_project()
            self.assertTrue(app.single_narrator())
            with patch('desktop.filedialog.asksaveasfilename',return_value=str(Path(folder)/'test.wav')), patch('desktop.export_audio') as export, patch.object(app,'run',side_effect=lambda work,done:work()):
                app.export()
                self.assertTrue(export.call_args.args[2]['single_narrator'])
            import json
            data = json.loads(Path(project).read_text(encoding='utf-8'))
            del data['settings']['voice_mode']
            Path(project).write_text(json.dumps(data),encoding='utf-8')
            with patch('desktop.filedialog.askopenfilename',return_value=project): app.load_project()
            self.assertFalse(app.single_narrator())

if __name__ == '__main__': unittest.main()
