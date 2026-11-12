# Loudness per 0.5 s, spectral-novelty peaks and beat tracking per segment. Usage: python3 audio_ana.py audio.wav
import librosa, numpy as np, sys
y,sr=librosa.load(sys.argv[1],sr=22050,mono=True)
hop=512
rms=librosa.feature.rms(y=y,hop_length=hop)[0]
t=librosa.frames_to_time(np.arange(len(rms)),sr=sr,hop_length=hop)
db=20*np.log10(rms+1e-6)
# print RMS dB every 0.25s
print("RMS dB per 0.5s:")
line=[]
for s in np.arange(0,len(y)/sr,0.5):
    i=np.searchsorted(t,s); j=np.searchsorted(t,s+0.5)
    line.append(f"{s:4.1f}:{db[i:j].mean():5.1f}")
for k in range(0,len(line),10): print("  ".join(line[k:k+10]))
# spectral novelty: cosine distance between mean mel spectra of 0.5s windows before/after
S=librosa.feature.melspectrogram(y=y,sr=sr,hop_length=hop,n_mels=64); L=np.log(S+1e-8)
w=int(0.6*sr/hop)
nov=np.zeros(L.shape[1])
for i in range(w,L.shape[1]-w):
    a=L[:,i-w:i].mean(1); b=L[:,i:i+w].mean(1)
    nov[i]=np.linalg.norm(a-b)/np.sqrt(len(a))
from scipy.signal import find_peaks
pk,_=find_peaks(nov,distance=int(1.0*sr/hop),prominence=0.25)
print("spectral novelty peaks (t, value):")
print(", ".join(f"{t[p]:.2f}({nov[p]:.2f})" for p in sorted(pk,key=lambda p:-nov[p])[:20]))
# beat tracking per segment
for a,b in [(0,10.23),(10.23,30.03),(30.03,69.7),(0,69.7)]:
    seg=y[int(a*sr):int(b*sr)]
    tempo,beats=librosa.beat.beat_track(y=seg,sr=sr,hop_length=hop)
    bt=librosa.frames_to_time(beats,sr=sr,hop_length=hop)+a
    print(f"seg {a}-{b}: tempo {np.atleast_1d(tempo)[0]:.1f}; beats: "+" ".join(f"{x:.2f}" for x in bt))
