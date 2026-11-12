# Active-picture rows/cols (letterbox measurement). Usage: python3 bars.py video.mp4 t1 t2 ...
import cv2, numpy as np, sys
p=sys.argv[1]; ts=[float(x) for x in sys.argv[2:]]
cap=cv2.VideoCapture(p)
for t in ts:
    cap.set(cv2.CAP_PROP_POS_MSEC,t*1000); ok,f=cap.read()
    g=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY).astype(float)
    rows=g.mean(1); cols=g.mean(0); rstd=g.std(1)
    # find first/last rows that are not uniform
    act=np.where(rstd>4)[0]
    top,bot=(act[0],act[-1]) if len(act) else (-1,-1)
    cact=np.where(g.std(0)>4)[0]
    print(f"t={t:6.2f} active rows {top}-{bot} (h={bot-top+1}) cols {cact[0]}-{cact[-1]} toprow mean={rows[:5].mean():.0f} botrow mean={rows[-5:].mean():.0f}")
