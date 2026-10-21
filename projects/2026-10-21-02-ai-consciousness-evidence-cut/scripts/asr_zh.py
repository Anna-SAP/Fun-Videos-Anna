"""Chinese narration ASR with segment timestamps (sherpa-onnx SenseVoice int8 + silero VAD).
usage: python3 asr_zh.py input_16k_mono.wav out.json
models -> ./models/: sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/, silero_vad.onnx
Used in project 03 to find the narration nodes and pauses of the main video, and in
project 01 for the plan 3 / plan 4 transcripts (homophones then fixed against the burned-in subtitles)."""
import sherpa_onnx, soundfile as sf, numpy as np, json, sys
m = "models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=f"{m}/model.int8.onnx", tokens=f"{m}/tokens.txt",
                                                     use_itn=True, language="zh", num_threads=4)
cfg = sherpa_onnx.VadModelConfig()
cfg.silero_vad.model = "models/silero_vad.onnx"
cfg.silero_vad.min_silence_duration = 0.3
cfg.silero_vad.min_speech_duration = 0.2
cfg.silero_vad.max_speech_duration = 12
cfg.sample_rate = 16000
vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=200)
a, sr = sf.read(sys.argv[1], dtype="float32")
if a.ndim > 1:
    a = a.mean(1)
ws = cfg.silero_vad.window_size
out = []

def drain():
    while not vad.empty():
        seg = vad.front
        s = rec.create_stream(); s.accept_waveform(sr, np.array(seg.samples)); rec.decode_stream(s)
        st = seg.start / sr
        out.append({"start": round(st, 2), "end": round(st + len(seg.samples) / sr, 2), "text": s.result.text})
        vad.pop()

for i in range(0, len(a), ws):
    vad.accept_waveform(a[i:i + ws]); drain()
vad.flush(); drain()
for o in out:
    print(f'{o["start"]:7.2f}-{o["end"]:7.2f} {o["text"]}')
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
