# Onset envelope + waveform around given cut times. Usage: python3 plot_cuts.py "[(t0,t1,[cuts...]),...]" out.png
# Run from a work dir holding ana/audio.wav (the source audio track).
import librosa, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
y,sr=librosa.load('ana/audio.wav',sr=22050,mono=True); hop=128
oenv=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
tt=librosa.frames_to_time(np.arange(len(oenv)),sr=sr,hop_length=hop)
on=librosa.onset.onset_detect(onset_envelope=oenv,sr=sr,hop_length=hop,units='time')
import sys; wins=eval(sys.argv[1]); out=sys.argv[2]
fig,axs=plt.subplots(len(wins),1,figsize=(22,13))
for ax,(a,b,cuts) in zip(axs,wins):
    m=(tt>=a)&(tt<=b); ax.plot(tt[m],oenv[m]/oenv[m].max(),lw=0.8)
    i,j=int(a*sr),int(b*sr); ts=np.arange(i,j)/sr; ax.plot(ts,y[i:j]/np.abs(y[i:j]).max()*0.5-0.7,lw=0.3,color='gray')
    for c in cuts: ax.axvline(c,color='r',lw=1.5)
    for o in on[(on>=a)&(on<=b)]: ax.axvline(o,color='g',lw=0.4,alpha=0.6)
    ax.set_xticks(np.arange(np.ceil(a*10)/10,b,0.1),minor=True); ax.set_xticks(np.arange(np.ceil(a*2)/2,b,0.5)); ax.grid(which='both',alpha=0.3); ax.set_xlim(a,b)
plt.tight_layout(); plt.savefig(out,dpi=80)

