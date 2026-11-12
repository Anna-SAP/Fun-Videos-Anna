# Tempo (onset autocorrelation) and key (chroma vs Krumhansl profiles) per segment.
# Run from a work dir holding ana/audio.wav (the source audio: ffmpeg -i src.mp4 -vn -ac 2 -ar 44100 ana/audio.wav).
import librosa, numpy as np
y,sr=librosa.load('ana/audio.wav',sr=22050,mono=True); hop=256
oenv=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
tt=librosa.frames_to_time(np.arange(len(oenv)),sr=sr,hop_length=hop)
def tempo_ac(a,b):
    i,j=np.searchsorted(tt,a),np.searchsorted(tt,b)
    o=oenv[i:j]-oenv[i:j].mean()
    ac=np.correlate(o,o,'full')[len(o)-1:]
    lags=np.arange(len(ac))*hop/sr
    res=[]
    for lo,hi in [(0.3,0.5),(0.5,0.75),(0.75,1.0)]:
        m=(lags>lo)&(lags<hi); k=np.argmax(ac*m); res.append((lags[k],60/lags[k],ac[k]/ac[0]))
    return res
segs=[(0,4.53),(4.53,5.6),(5.67,10.23),(10.23,20),(20,30.0),(30.03,45),(45,60),(60,69.7)]
for a,b in segs:
    print(f"{a:5.2f}-{b:5.2f}: "+"  ".join(f"lag {l:.3f}s={bpm:.1f}bpm r={r:.2f}" for l,bpm,r in tempo_ac(a,b)))
chroma=librosa.feature.chroma_cqt(y=y,sr=sr,hop_length=512)
ct=librosa.frames_to_time(np.arange(chroma.shape[1]),sr=sr,hop_length=512)
names='C C# D D# E F F# G G# A A# B'.split()
maj=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]); mnr=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
def key(a,b):
    m=chroma[:,(ct>=a)&(ct<b)].mean(1)
    best=[]
    for k in range(12):
        best.append((np.corrcoef(m,np.roll(maj,k))[0,1],names[k]+' maj'))
        best.append((np.corrcoef(m,np.roll(mnr,k))[0,1],names[k]+' min'))
    best.sort(reverse=True); return best[:2], m
for a,b in [(0,5.6),(5.67,10.23),(10.23,30.0),(30.03,69.7)]:
    bk,m=key(a,b); print(f"key {a}-{b}: {bk[0][1]} ({bk[0][0]:.2f}) / {bk[1][1]} ({bk[1][0]:.2f})")
