LANGUAGES = {
    '英语 / English': 'en-',
    '葡萄牙语（巴西） / Português (Brasil)': 'pt-BR-',
    '葡萄牙语（葡萄牙） / Português (Portugal)': 'pt-PT-',
    '西班牙语（全部地区） / Español': 'es-',
    '西班牙语（西班牙） / Español (España)': 'es-ES-',
    '西班牙语（墨西哥） / Español (México)': 'es-MX-',
    '中文 / Chinese': 'zh-',
    '法语 / Français': 'fr-',
    '德语 / Deutsch': 'de-',
    '意大利语 / Italiano': 'it-',
    '日语 / Japanese': 'ja-',
    '韩语 / Korean': 'ko-',
    '阿拉伯语 / Arabic': 'ar-',
    '印地语 / Hindi': 'hi-',
    '全部语言 / All languages': '',
}
DEFAULT_LANGUAGE = '英语 / English'

def language_options(voices):
    options = dict(LANGUAGES)
    for locale in sorted({'-'.join(voice.split('-')[:2]) for voice in voices}):
        options.setdefault(locale, locale + '-')
    return options

def matching_voices(voices, language, search=''):
    prefix = language_options(voices).get(language, 'en-')
    return [v for v in voices if v.startswith(prefix) and search.strip().lower() in v.lower()]

def default_voice(voices, language):
    from audio_core import DEFAULT_VOICE
    choices = matching_voices(voices, language)
    return DEFAULT_VOICE if DEFAULT_VOICE in choices else (choices[0] if choices else DEFAULT_VOICE)

def preview_text(voice):
    return {'en':'Hello, this is a preview of this character’s voice.',
            'pt':'Olá, esta é uma amostra da voz desta personagem.',
            'es':'Hola, esta es una muestra de la voz de este personaje.',
            'zh':'你好，这是这个角色的配音试听。',
            'fr':'Bonjour, voici un aperçu de la voix de ce personnage.',
            'de':'Hallo, dies ist eine Vorschau dieser Stimme.',
            'it':'Ciao, questa è una prova della voce.',
            'ja':'こんにちは、これは音声のサンプルです。',
            'ko':'안녕하세요. 이 목소리를 들어 보세요.'}.get(voice.split('-')[0], 'Hello, this is a voice preview.')
