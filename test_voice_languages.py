import unittest
from edge_voices import VOICES
from voice_languages import matching_voices, default_voice, DEFAULT_LANGUAGE, preview_text

class VoiceLanguageTests(unittest.TestCase):
    def test_english_default_and_regional_choices(self):
        self.assertEqual(default_voice(VOICES,DEFAULT_LANGUAGE),'en-US-AriaNeural')
        self.assertGreater(len(matching_voices(VOICES,DEFAULT_LANGUAGE)),10)
        for language,prefix in [('pt-BR','pt-BR-'),('pt-PT','pt-PT-'),('es-MX','es-MX-'),('es-ES','es-ES-')]:
            choices = matching_voices(VOICES,language)
            self.assertTrue(choices)
            self.assertTrue(all(v.startswith(prefix) for v in choices))

    def test_search_and_preview(self):
        self.assertEqual(matching_voices(VOICES,DEFAULT_LANGUAGE,'en-US-AriaNeural'),['en-US-AriaNeural'])
        self.assertEqual(matching_voices(VOICES,'pt-BR','en-US-AriaNeural'),[])
        self.assertTrue(preview_text('pt-BR-FranciscaNeural').startswith('Olá'))
        self.assertTrue(preview_text('es-MX-DaliaNeural').startswith('Hola'))

if __name__ == '__main__': unittest.main()
