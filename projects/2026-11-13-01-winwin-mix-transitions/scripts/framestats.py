# Per-frame stats (luma, saturation, histogram distance, pixel difference). Usage: python3 framestats.py video.mp4 out.json
import cv2, numpy as np, sys, json
p=sys.argv[1]; out=sys.argv[2]
cap=cv2.VideoCapture(p); fps=cap.get(cv2.CAP_PROP_FPS)
prev=None; prevsmall=None; rows=[]
i=0
while True:
    ok,f=cap.read()
    if not ok: break
    small=cv2.resize(f,(160,90),interpolation=cv2.INTER_AREA)
    hsv=cv2.cvtColor(small,cv2.COLOR_BGR2HSV)
    h=cv2.calcHist([hsv],[0,1,2],None,[16,8,8],[0,180,0,256,0,256]); h=cv2.normalize(h,h).flatten()
    g=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY).astype(np.float32)
    luma=float(g.mean()); sat=float(hsv[...,1].mean())
    if prev is None: hd=0.0; pd=0.0
    else:
        hd=float(cv2.compareHist(prev,h,cv2.HISTCMP_BHATTACHARYYA))
        pd=float(np.abs(g-prevsmall).mean())
    rows.append(dict(i=i,t=i/fps,luma=luma,sat=sat,hd=hd,pd=pd))
    prev=h; prevsmall=g; i+=1
json.dump(dict(fps=fps,rows=rows),open(out,'w'))
print(i,fps)
