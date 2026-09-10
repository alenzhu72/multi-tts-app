import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from desktop import App
from audio_core import NARRATOR

class DesktopModeTests(unittest.TestCase):
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
