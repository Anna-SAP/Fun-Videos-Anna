"""English ASR with word-level timestamps (sherpa-onnx NeMo Parakeet-TDT 0.6B v2 int8 + silero VAD).

Writes one JSON object per speech segment (JSON Lines) as soon as it is decoded, so a
long interview can be searched while transcription is still running:
  {"start": s, "end": s, "text": "...", "tokens": [...], "ts": [absolute token times]}

usage: python3 asr_en.py input_16k_mono.wav out.jsonl [threads=8]
models (GitHub releases of k2-fsa/sherpa-onnx, asr-models):
  sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2, silero_vad.onnx  -> ./models/
Used in project 03 on the 2 h 47 min JRE #2541 audio, transcribed in chunks with the
most relevant range (36:40–66:40) first; chunk offsets are added back afterwards.
"""
import sherpa_onnx, soundfile as sf, numpy as np, json, sys, time

m = "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=f"{m}/encoder.int8.onnx", decoder=f"{m}/decoder.int8.onnx", joiner=f"{m}/joiner.int8.onnx",
    tokens=f"{m}/tokens.txt", model_type="nemo_transducer",
    num_threads=int(sys.argv[3]) if len(sys.argv) > 3 else 8)
cfg = sherpa_onnx.VadModelConfig()
cfg.silero_vad.model = "models/silero_vad.onnx"
cfg.silero_vad.min_silence_duration = 0.25
cfg.silero_vad.min_speech_duration = 0.2
cfg.silero_vad.max_speech_duration = 20
cfg.sample_rate = 16000
vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=600)

a, sr = sf.read(sys.argv[1], dtype="float32")
if a.ndim > 1:
    a = a.mean(1)
ws = cfg.silero_vad.window_size
t0 = time.time()
fo = open(sys.argv[2], "w")


def drain():
    while not vad.empty():
        seg = vad.front
        s = rec.create_stream(); s.accept_waveform(sr, np.array(seg.samples)); rec.decode_stream(s)
        st = seg.start / sr
        r = s.result
        o = {"start": round(st, 3), "end": round(st + len(seg.samples) / sr, 3), "text": r.text,
             "tokens": list(r.tokens), "ts": [round(st + x, 3) for x in r.timestamps]}
        fo.write(json.dumps(o, ensure_ascii=False) + "\n"); fo.flush()
        vad.pop()


for i in range(0, len(a), ws):
    vad.accept_waveform(a[i:i + ws]); drain()
vad.flush(); drain()
print("done", time.time() - t0)
