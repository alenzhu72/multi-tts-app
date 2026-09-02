from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "5173"))


def run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def list_system_voices() -> list[dict[str, str]]:
    script = r"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $synth.GetInstalledVoices() | ForEach-Object {
  $info = $_.VoiceInfo
  [PSCustomObject]@{
    id = $info.Name
    name = $info.Name
    lang = $info.Culture.Name
    gender = $info.Gender.ToString()
  }
}
$voices | ConvertTo-Json -Depth 3
"""
    result = run_powershell(script)
    if result.returncode != 0:
        return []
    raw = result.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


def synthesize_wav(text: str, voice: str, output_path: Path) -> None:
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ({ps_quote(voice)} -ne '') {{ $synth.SelectVoice({ps_quote(voice)}) }}
$synth.SetOutputToWaveFile({ps_quote(str(output_path))})
$synth.Speak({ps_quote(text)})
$synth.Dispose()
"""
    result = run_powershell(script)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "System voice synthesis failed")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Windows did not return a WAV file. No compatible SAPI voice may be installed.")


def safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return name[:80] or uuid.uuid4().hex


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/voices":
            self.send_json(list_system_voices())
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/speak":
            payload = self.read_json()
            text = str(payload.get("text", "")).strip()
            voice = str(payload.get("voice", "")).strip()
            if not text:
                self.send_error(400, "Missing text")
                return
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                wav_path = Path(tmp) / "preview.wav"
                try:
                    synthesize_wav(text, voice, wav_path)
                except RuntimeError as error:
                    self.send_error(500, str(error))
                    return
                self.send_bytes(wav_path.read_bytes(), "audio/wav")
            return

        if self.path == "/api/export-wav":
            payload = self.read_json()
            cues = payload.get("cues") or []
            roles = payload.get("roles") or {}
            if not cues:
                self.send_error(400, "Missing cues")
                return
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                tmp_path = Path(tmp)
                manifest = []
                for cue in cues:
                    index = int(cue.get("index", len(manifest) + 1))
                    role = str(cue.get("role", "A"))
                    text = str(cue.get("text", "")).strip()
                    speaker = str(cue.get("speaker", ""))
                    voice = str(roles.get(role, ""))
                    wav_name = f"{index:04d}_{safe_filename(role)}.wav"
                    wav_path = tmp_path / wav_name
                    try:
                        synthesize_wav(text, voice, wav_path)
                    except RuntimeError as error:
                        self.send_error(500, str(error))
                        return
                    manifest.append(
                        {
                            "file": wav_name,
                            "index": index,
                            "time": cue.get("time", ""),
                            "speaker": speaker,
                            "role": role,
                            "voice": voice,
                            "text": text,
                        }
                    )

                zip_path = tmp_path / "smart-cast-wav.zip"
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for item in manifest:
                        archive.write(tmp_path / item["file"], item["file"])
                    archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                self.send_bytes(zip_path.read_bytes(), "application/zip")
            return

        self.send_error(404)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def send_json(self, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(data, "application/json; charset=utf-8")

    def send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving SRT voice casting tool at http://127.0.0.1:{PORT}")
    server.serve_forever()
