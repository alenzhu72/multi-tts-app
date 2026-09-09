"""Deterministic text segmentation and estimated subtitle timing."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from audio_core import parse_srt, NARRATOR


def read_text(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('gb18030')


def duration_ms(value):
    """Accept seconds or MM:SS / HH:MM:SS, with millisecond precision."""
    value = str(value).strip()
    if not value:
        return None
    try:
        if not re.fullmatch(r'\d+(?::\d{1,2}){0,2}(?:\.\d{1,3})?', value):
            raise ValueError
        parts = [Decimal(p) for p in value.split(':')]
        if any(p >= 60 for p in parts[1:]):
            raise ValueError
        seconds = Decimal(0)
        for part in parts:
            seconds = seconds * 60 + part
        result = int((seconds * 1000).to_integral_value(rounding=ROUND_HALF_UP))
        if not 0 < result <= 7 * 24 * 3600 * 1000:
            raise ValueError
        return result
    except (ValueError, InvalidOperation):
        raise ValueError('总时长需为正数秒或 MM:SS / HH:MM:SS，最多 7 天。 / Enter positive seconds or MM:SS / HH:MM:SS, up to 7 days.') from None


def timestamp(ms):
    hours, rest = divmod(ms, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, millis = divmod(rest, 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'


def to_srt(cues, include_speakers=False):
    blocks = []
    for i, cue in enumerate(cues, 1):
        # Blank lines delimit SRT blocks; remove blank lines within a cue.
        text = '\n'.join(line for line in cue['text'].strip().splitlines() if line.strip())
        if not text or cue['end'] <= cue['start'] or cue['start'] < 0:
            raise ValueError('字幕文本或时间轴无效。 / Invalid subtitle text or timing.')
        if include_speakers and cue['speaker'] != NARRATOR:
            text = f'[{cue["speaker"]}] {text}'
        blocks.append(f'{i}\n{timestamp(cue["start"])} --> {timestamp(cue["end"])}\n{text}')
    if not blocks:
        raise ValueError('没有可导出的字幕。 / No subtitles to export.')
    return '\n\n'.join(blocks) + '\n'


def split_text(text):
    """Keep explicit paragraph speaker labels across sentence splits."""
    segments = []
    for line in text.lstrip('\ufeff').splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = parse_srt('1\n00:00:00,000 --> 00:00:01,000\n' + line)[0]
        # Decimal points stay intact; English full stops split at whitespace.
        sentences = re.findall(r'.+?(?:[。！？!?]+[”’"\']*|\.(?=\s|$)|$)', parsed['text'])
        for sentence in sentences:
            sentence = sentence.strip()
            # Bound long paragraphs; prefer spaces and comma boundaries.
            while len(sentence) > 100:
                cut = max(sentence.rfind(' ', 35, 100), sentence.rfind('，', 35, 100), sentence.rfind(',', 35, 100))
                cut = cut + 1 if cut >= 0 else 100
                segments.append((sentence[:cut].strip(), parsed['speaker']))
                sentence = sentence[cut:].strip()
            if sentence:
                segments.append((sentence, parsed['speaker']))
    return segments


def text_to_cues(text, total_duration=''):
    segments = split_text(text)
    if not segments:
        raise ValueError('请输入文字或导入 TXT。 / Enter text or import a TXT file.')
    # Estimate Chinese at 4 characters/sec and Latin words at 2.5 words/sec.
    weights = []
    for content, _ in segments:
        cjk = len(re.findall(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]', content))
        words = len(re.findall(r'[A-Za-z0-9]+(?:[\x27’-][A-Za-z0-9]+)*', content))
        weights.append(max(1000, cjk * 250 + words * 400 + 300))
    total = duration_ms(total_duration)
    if total is None:
        lengths = weights
    else:
        if total < len(segments):
            raise ValueError('总时长过短，每条字幕至少需要 1 毫秒。 / Duration is too short: each cue needs at least 1 ms.')
        # Reserve 1 ms per cue and distribute the remainder with exact integer boundaries.
        remaining, weight_sum, cumulative, previous = total - len(segments), sum(weights), 0, 0
        lengths = []
        for weight in weights:
            cumulative += weight
            boundary = remaining * cumulative // weight_sum
            lengths.append(1 + boundary - previous)
            previous = boundary
    cues, start = [], 0
    for i, ((content, speaker), length) in enumerate(zip(segments, lengths), 1):
        cues.append(dict(id=i, start=start, end=start+length, text=content, speaker=speaker))
        start += length
    return cues
