from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math, random, textwrap, subprocess, json, concurrent.futures, sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'bayes_script_work' / 'edit'
OUT = ROOT / '贝叶斯_理论解析与实证实录'
WORK.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
W,H = 1080,1920
FPS = 30
CREAM='#F2EFDF'; INK='#243431'; TEAL='#138D94'; ORANGE='#C76436'; GRAY='#75807A'; LINE='#D4D8C9'
FONTS=Path('C:/Windows/Fonts')
def font(n,bold=False,latin=False):
    return ImageFont.truetype(str(FONTS/('segoeuib.ttf' if bold else 'segoeui.ttf') if latin else FONTS/('msyhbd.ttc' if bold else 'msyh.ttc')),n)

random.seed(42)
BASE=Image.new('RGB',(W,H),CREAM)
bd=ImageDraw.Draw(BASE)
for y in range(12,H,25):
    for x in range(12,W,25): bd.ellipse((x,y,x+2,y+2),fill='#DCDDCB')
for _ in range(14000):
    x=random.randrange(W); y=random.randrange(H)
    bd.point((x,y),fill=random.choice(['#E4E2D2','#E8E6D6','#F8F5E7']))

def txt(im,xy,s,n=48,fill=INK,bold=False,anchor=None,latin=False,spacing=12):
    ImageDraw.Draw(im).multiline_text(xy,s,font=font(n,bold,latin),fill=fill,anchor=anchor,spacing=spacing)
def fit(im,box,s,n=48,fill=INK,bold=False):
    x,y,mw=box
    while font(n,bold).getlength(s)>mw:n-=1
    txt(im,(x,y),s,n,fill,bold)
def line(im,xy,fill=LINE,width=2): ImageDraw.Draw(im).line(xy,fill=fill,width=width)
def panel(im,box,fill='#F9F7EC',outline=LINE,r=24):
    ImageDraw.Draw(im).rounded_rectangle(box,radius=r,fill=fill,outline=outline,width=2)
def pill(im,xy,s,color=TEAL):
    x,y=xy; sw=font(28,True).getlength(s)
    ImageDraw.Draw(im).rounded_rectangle((x,y,x+sw+40,y+52),radius=26,fill=color)
    txt(im,(x+20,y+7),s,28,'#FFFFFF',True)
def base(kind,chapter):
    im=BASE.copy()
    txt(im,(64,54),'BAYESIAN  /  理论解析 + 实证实录',28,TEAL,True)
    line(im,(64,112,1016,112),TEAL,3)
    txt(im,(64,137),'“非常贝叶斯”',58,INK,True)
    pill(im,(64,235),kind)
    txt(im,(1016,248),chapter,26,GRAY,anchor='ra')
    line(im,(64,1838,1016,1838),LINE,2)
    txt(im,(64,1860),'素材：非常贝叶斯.mp4 × clip_贝叶斯.mp4',23,GRAY)
    return im
def still(sec):
    dest=WORK/f'still_{sec:.2f}.png'
    if not dest.exists():
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(sec),'-i',str(ROOT/'clip_贝叶斯.mp4'),'-frames:v','1','-update','1','-y',str(dest)],check=True)
    return Image.open(dest).convert('RGB')
def paste_still(im,sec,box):
    pic=still(sec).resize((box[2],box[3]),Image.Resampling.LANCZOS)
    im.paste(pic,box[:2]); ImageDraw.Draw(im).rectangle((box[0],box[1],box[0]+box[2]-1,box[1]+box[3]-1),outline=LINE,width=2)
def save(im,name):
    p=WORK/f'{name}.png';im.save(p);return p

# Each graphic makes an argument, while the interview remains an intact landscape image.
im=base('开场 · 一句夸奖，两个层次','00 / INTRO')
txt(im,(64,350),'夸一个人，\n为什么要用',83,INK,True,spacing=22)
txt(im,(64,575),'贝叶斯定理？',86,ORANGE,True)
paste_still(im,62.8,(64,820,952,536))
pill(im,(88,1392),'VERY BAYESIAN',TEAL)
txt(im,(64,1492),'先听原话，再拆解推理。',43,INK,True)
save(im,'hook')

def evidence(name,title,chapter,note,subnote,tag):
    im=base('原始访谈 · 英文原声',chapter)
    fit(im,(64,332,952),title,58,INK,True)
    # Source video occupies (28,460,1024,576); all original pixels and subtitles are preserved.
    panel(im,(28,460,1052,1036),'#121B18','#263A34',0)
    txt(im,(64,415),tag,25,GRAY)
    line(im,(64,1065,1016,1065),LINE,2)
    panel(im,(64,1485,1016,1768))
    ImageDraw.Draw(im).rounded_rectangle((64,1485,75,1768),radius=4,fill=TEAL)
    txt(im,(104,1520),'这一句在论证什么？',28,TEAL,True)
    txt(im,(104,1573),note,44,INK,True,spacing=16)
    txt(im,(104,1704),subnote,27,GRAY)
    return save(im,name)

evidence('e1','第 1 句：先限定比较范围','01 / EVIDENCE','先说明观察的边界，\n再给出对 Mark 的评价。','comparison set = 可用于比较的样本','源片 00:01.95—00:04.60')
evidence('e2','第 2 句：从新信息到新行动','02 / EVIDENCE','吸收信息 → 更新判断\n→ 按新判断行动','这是访谈对 Mark 的描述','源片 00:52.30—00:58.70')
evidence('e3','于是，这句评价出现了','03 / EVIDENCE','“贝叶斯”在这里，\n是在夸他愿意更新判断。','把统计学语言，用作对认知习惯的比喻','源片 00:58.70—01:04.73')
evidence('e4','第 3 句：从理论滑向双关','04 / EVIDENCE','同一个词，\n从统计术语切到另一层意思。','接下来逐词拆开 prior / posterior','源片 01:05.10—01:10.65')

im=base('理论解析 · 信息如何改变行动','01 / ANALYSIS')
txt(im,(64,330),'“转向”的关键，\n是它由什么推动。',62,INK,True,spacing=17)
for i,(en,cn,col) in enumerate([('INFORMATION','吸收新信息',ORANGE),('BELIEF','更新判断',TEAL),('ACTION','改变行动',TEAL)]):
    yy=570+i*122
    panel(im,(64,yy,1016,yy+98))
    txt(im,(92,yy+21),f'0{i+1}',40,col,True,latin=True)
    txt(im,(192,yy+23),cn,40,INK,True)
    txt(im,(975,yy+35),en,23,col,anchor='ra',latin=True)
    if i<2:txt(im,(527,yy+97),'↓',32,col)
paste_still(im,54.3,(64,1015,952,536))
txt(im,(64,1587),'对应原话：updates his worldview',30,GRAY)
save(im,'actions')

im=base('理论解析 · 贝叶斯更新','02 / ANALYSIS')
txt(im,(64,333),'先验 × 似然 → 后验',62,INK,True)
panel(im,(64,455,1016,690))
ImageDraw.Draw(im).text((540,493),'P(θ | D) ∝ P(D | θ) · P(θ)',font=ImageFont.truetype(str(FONTS/'cambria.ttc'),56,index=1),fill=TEAL,anchor='ma')
txt(im,(540,591),'后验          似然          先验',37,INK,anchor='ma')
txt(im,(64,746),'先验：看到本次证据之前的判断',36,ORANGE,True)
txt(im,(64,811),'似然：该判断有多能解释新证据',36,GRAY,True)
txt(im,(64,876),'后验：结合新证据之后的判断',36,TEAL,True)
# Actual conjugate Gaussian example, shown only as a conceptual diagram.
X0,Y0,X1,Y1=110,1000,970,1350
line(im,(X0,Y1,X1,Y1),GRAY,3)
line(im,(X0,Y1,X0,Y0),GRAY,3)
def curve(mu,sd,col,width):
    pts=[]
    for k in range(600):
        x=-3+6*k/599
        val=math.exp(-.5*((x-mu)/sd)**2)/(sd*math.sqrt(2*math.pi))
        pts.append((X0+(X1-X0)*k/599,Y1-val*510))
    ImageDraw.Draw(im).line(pts,fill=col,width=width,joint='curve')
curve(-.8,.9,ORANGE,5);curve(.7,.7,'#A4ACA2',4)
pv=1/(1/.9**2+1/.7**2);pm=pv*(-.8/.9**2+.7/.7**2)
curve(pm,math.sqrt(pv),TEAL,7)
txt(im,(250,1377),'先验',30,ORANGE,True)
txt(im,(490,1377),'后验',30,TEAL,True)
txt(im,(745,1377),'似然',30,GRAY,True)
txt(im,(64,1456),'先验 ≠ 偏见',54,INK,True)
txt(im,(64,1541),'更新判断，也不等于清空已有认知。',33,GRAY)
txt(im,(64,1595),'曲线为理论示意，不代表访谈测量数据。',24,GRAY)
save(im,'bayes')

im=base('理论解析 · 逐词拆解双关','03 / ANALYSIS')
txt(im,(64,333),'同一个 posterior，\n为什么能接上笑话？',60,INK,True,spacing=16)
panel(im,(64,552,1016,815))
txt(im,(102,587),'统计学语境',29,TEAL,True)
txt(im,(130,661),'prior',62,ORANGE,True,latin=True)
txt(im,(469,675),'→',56,GRAY)
txt(im,(611,661),'posterior',62,TEAL,True,latin=True)
txt(im,(139,760),'先验',34,INK)
txt(im,(680,760),'后验',34,INK)
panel(im,(64,850,1016,1080))
txt(im,(102,880),'另一层词义',29,ORANGE,True)
txt(im,(112,950),'posterior',62,TEAL,True,latin=True)
txt(im,(610,960),'也可以指“臀部”',40,INK,True)
paste_still(im,69.2,(64,1120,952,536))
save(im,'wordplay')

im=base('访谈回看 · 双关的落点','03 / REACTION')
txt(im,(64,333),'双关落地，回到现场。',59,INK,True)
panel(im,(28,460,1052,1036),'#121B18','#263A34',0)
panel(im,(64,1130,1016,1320))
txt(im,(105,1160),'POSTERIOR  /  统计学',27,TEAL,True)
txt(im,(105,1222),'后验：结合证据后的判断',46,INK,True)
panel(im,(64,1360,1016,1550))
txt(im,(105,1390),'POSTERIOR  /  另一层词义',27,ORANGE,True)
txt(im,(105,1452),'臀部：笑点由此产生',46,INK,True)
save(im,'reaction')

im=base('收束 · 把术语还原成动作','04 / TAKEAWAY')
txt(im,(64,358),'先有判断。\n再看证据。\n据此更新。',104,INK,True,spacing=32)
line(im,(64,884,1016,884),TEAL,5)
txt(im,(64,961),'“非常贝叶斯”',66,TEAL,True)
txt(im,(64,1076),'是这段访谈给出的评价。',42,INK)
txt(im,(64,1167),'真正值得带走的，是：',42,INK)
txt(im,(64,1271),'让判断接受证据的修正。',51,ORANGE,True)
txt(im,(64,1511),'THEORY  ×  ORIGINAL INTERVIEW',31,TEAL,True,latin=True)
txt(im,(64,1575),'逐句拆解 · 原声佐证 · 中英字幕',33,GRAY)
save(im,'end')

# Cover uses the same design language as the finished film.
cover=Image.open(WORK/'hook.png').copy()
ImageDraw.Draw(cover).rectangle((30,1620,1050,1810),fill=CREAM)
txt(cover,(64,1650),'理论解析 × 访谈实录',46,TEAL,True)
cover.save(OUT/'封面.jpg',quality=95)

def N(a,b,s):return {'a':a,'b':b,'zh':s}
def E(a,b,en,zh):return {'a':a,'b':b,'en':en,'zh':zh}
SCENES=[
 {'id':'01_hook','plate':'hook','src':'theory','start':0,'end':5.85,'style':'narration','cap':[
 N(.2,1.45,'为什么硅谷大佬，'),N(1.45,2.75,'会用“贝叶斯”这个'),N(2.75,4.35,'硬核的统计学词汇，'),N(4.35,5.85,'来夸奖扎克伯格？')]},
 {'id':'02_sample','plate':'e1','src':'clip','start':1.95,'end':4.60,'style':'evidence','cap':[
 E(0,2.65,"Um, well, I don't have a huge comparison set.",'嗯，我能拿来比较的样本其实不多。')]},
 {'id':'03_actions','plate':'actions','src':'theory','start':16.5,'end':26.95,'style':'narration','cap':[
 N(0,1.23,'一旦接纳新理念，'),N(1.23,3.0,'他就能果断推翻过往，'),N(3.0,4.2,'迅速掉头。'),N(4.2,5.9,'也就是像机器一样，'),N(5.9,7.4,'大口“吸收”新信息，'),N(7.4,9.0,'并据此彻底“刷新”'),N(9.0,10.45,'自己的世界观。')]},
 {'id':'04_update','plate':'e2','src':'clip','start':52.3,'end':58.7,'style':'evidence','cap':[
 E(0,3.8,'Mark actually ingests new information and fully updates his worldview and then','Mark 确实会吸收新信息，\n充分更新自己的世界观，然后'),
 E(3.8,6.4,'acts in accordance with the newly installed worldview.','按照更新后的世界观行动。')]},
 {'id':'05_bayesian','plate':'e3','src':'clip','start':58.7,'end':64.73,'style':'evidence','cap':[
 E(0,3.4,'Very Bayesian. And then willing to take— Very Bayesian.','非常贝叶斯。然后愿意去——\n非常贝叶斯。'),
 E(3.4,6.03,"Very Bayesian. I've never gotten such a nice compliment.",'非常贝叶斯。\n我还从没听过这么好的夸奖。')]},
 {'id':'06_theorem','plate':'bayes','src':'theory','start':27.15,'end':37.98,'style':'narration','cap':[
 N(0,1.0,'这种特质，'),N(1,4.0,'被精确总结为“非常贝叶斯”。'),N(4,5.65,'它的核心奥义在于：'),N(5.65,7.3,'绝不死守偏见，'),N(7.3,8.75,'而是根据新证据，'),N(8.75,10.83,'无情地修正自己的判断。')]},
 {'id':'07_joke','plate':'e4','src':'clip','start':65.1,'end':70.65,'style':'evidence','cap':[
 E(0,3.5,'What lovely priors you have.','你的“先验”真漂亮。'),E(3.5,5.55,'Yeah. Posterior.','对。后验。\n（posterior 也可指“臀部”）')]},
 {'id':'08_terms','plate':'wordplay','src':'theory','start':38.3,'end':46.15,'style':'narration','cap':[
 N(0,1.3,'对话的结尾，'),N(1.3,3.0,'更是抛出了一个绝妙的双关。'),N(3.0,4.35,'在贝叶斯理论中，'),N(4.35,7.85,'“prior”和“posterior”\n代表先验与后验。')]},
 # Omit the original narrator's inaccurate description of posterior as slang.
 {'id':'09_meaning','plate':'wordplay','src':'theory','start':47.6,'end':50.6,'style':'narration','cap':[
 N(0,3.0,'“posterior”恰好\n也是“臀部”的意思。')]},
 {'id':'10_laugh','plate':'reaction','src':'theory','start':50.78,'end':53.12,'style':'reaction','video_start':70.55,'cap':[
 N(0,2.34,'这就是为什么大家会哄堂大笑。')]},
 {'id':'11_end','plate':'end','src':None,'start':0,'end':3.6,'style':'end','cap':[]},
]

def dur(s):return round((s['end']-s['start'])*FPS)/FPS
def ass_time(t):
    cs=round(t*100);return f'{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}'
def srt_time(t):
    ms=round(t*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
def wrap_cjk(s,limit):
    return '\\N'.join('\n'.join(textwrap.wrap(a,width=limit,break_long_words=False,break_on_hyphens=False)) if a.isascii() else '\n'.join(a[i:i+limit] for i in range(0,len(a),limit)) for a in s.split('\n')).replace('\n','\\N')
def wrap_en(s,width=38):return '\\N'.join(textwrap.wrap(s,width,break_long_words=False,break_on_hyphens=False))
ASS_HEADER='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narration,Microsoft YaHei,48,&H00313424,&H00313424,&H00DFEFF2,&H00DFEFF2,-1,0,0,0,100,100,0,0,1,7,0,8,64,64,0,1
Style: English,Segoe UI,44,&H00313424,&H00313424,&H00DFEFF2,&H00DFEFF2,-1,0,0,0,100,100,0,0,1,0,0,8,64,64,0,1
Style: Translation,Microsoft YaHei,43,&H00948D13,&H00948D13,&H00DFEFF2,&H00DFEFF2,-1,0,0,0,100,100,0,0,1,0,0,8,64,64,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''

def make_ass(s):
    a=ASS_HEADER
    for c in s['cap']:
        start,end=ass_time(c['a']),ass_time(min(c['b'],dur(s)))
        if 'en'in c:
            a+=f'Dialogue: 0,{start},{end},English,,0,0,0,,{{\\an8\\pos(540,1104)}}{wrap_en(c["en"])}\n'
            a+=f'Dialogue: 1,{start},{end},Translation,,0,0,0,,{{\\an8\\pos(540,1314)}}{wrap_cjk(c["zh"],21)}\n'
        else:
            yy=1745 if s['style']=='reaction' else 1680
            a+=f'Dialogue: 1,{start},{end},Narration,,0,0,0,,{{\\an8\\pos(540,{yy})}}{wrap_cjk(c["zh"],19)}\n'
    p=WORK/(s['id']+'.ass');p.write_text(a,encoding='utf-8-sig');return p

def render(s):
    duration=dur(s);frames=round(duration*FPS)
    dest=WORK/(s['id']+'.mp4')
    if '--resume'in sys.argv and f'--redo={s["id"]}' not in sys.argv and dest.exists() and dest.stat().st_size>1000:return dest
    ass=make_ass(s)
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y']
    if s['src']:
        src=ROOT/('非常贝叶斯.mp4' if s['src']=='theory' else 'clip_贝叶斯.mp4')
        cmd+=['-ss',str(s['start']),'-t',str(duration),'-i',str(src)]
    else:
        cmd+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    cmd+=['-loop','1','-framerate','30','-i',str(WORK/(s['plate']+'.png'))]
    filters=[]
    if s['style']=='evidence':
        filters+=['[0:v]scale=1024:576:flags=lanczos,setsar=1,fps=30,setpts=PTS-STARTPTS[clip]', '[1:v][clip]overlay=28:460:shortest=1[canvas]']
    elif s['style']=='reaction':
        cmd+=['-ss',str(s['video_start']),'-t',str(duration),'-i',str(ROOT/'clip_贝叶斯.mp4')]
        filters+=['[2:v]scale=1024:576:flags=lanczos,setsar=1,fps=30,setpts=PTS-STARTPTS[clip]','[1:v][clip]overlay=28:460:shortest=1[canvas]']
    else:filters+=['[1:v]null[canvas]']
    # A thin advancing line gives every shot a visible sense of time without covering evidence.
    vf=f"[canvas]ass='{ass.name}',drawbox=x=64:y=1813:w=952:h=4:color=0xD4D8C9:t=fill,drawbox=x=64:y=1813:w=952:h=4:color=0x138D94:t=fill:enable='gte(t,{duration-0.1})'"
    if s['style']=='end':vf+=f',fade=t=out:st={duration-.5}:d=0.5'
    filters+=[vf+'[v]']
    if s['src']:
        af=f'[0:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000,apad,atrim=duration={duration},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={max(0,duration-.025)}:d=0.025[a]'
    else:af=f'[0:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a]'
    filters.append(af)
    cmd+=['-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-frames:v',str(frames),'-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','19','-threads','5','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-video_track_timescale','15360','-movflags','+faststart',str(dest)]
    log=WORK/(s['id']+'.log')
    with log.open('w',encoding='utf-8') as f:
        p=subprocess.run(cmd,cwd=WORK,stdout=f,stderr=f)
    if p.returncode:raise RuntimeError(f'{s["id"]} failed: {log.read_text(encoding="utf-8")[-2000:]}')
    print('RENDERED',s['id'],f'{duration:.3f}s',flush=True)
    return dest

if __name__=='__main__':
    (WORK/'edit_manifest.json').write_text(json.dumps(SCENES,ensure_ascii=False,indent=2),encoding='utf-8')
    if '--assets-only'in sys.argv:sys.exit(0)
    targets=SCENES[:2] if '--preview'in sys.argv else SCENES
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:paths=list(pool.map(render,targets))
    if '--preview'in sys.argv:sys.exit(0)
    concat=WORK/'concat.txt'
    concat.write_text('\n'.join("file '"+p.name+"'\nduration "+f'{dur(s):.8f}' for p,s in zip(paths,SCENES)),encoding='utf-8')
    final=OUT/'非常贝叶斯_理论解析与实证实录.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(concat),'-c:v','copy','-c:a','aac','-b:a','192k','-af','aresample=async=1:first_pts=0','-t',str(sum(dur(s) for s in SCENES)),'-movflags','+faststart','-metadata','title=非常贝叶斯｜理论解析与实证实录','-metadata','comment=根据用户提供的两段素材剪辑；保留中文解析及访谈英文原声；术语图解为理论示意。',str(final)],check=True,cwd=WORK)
    elapsed=0;entries=[];edits=[]
    for s in SCENES:
        d=dur(s)
        edits.append({'shot':s['id'],'out_start':elapsed,'out_end':elapsed+d,'source':s['src'],'source_start':s['start'],'source_end':s['end']})
        for c in s['cap']:
            content=(c.get('en','')+'\n' if 'en'in c else '')+c['zh']
            entries.append(f'{len(entries)+1}\n{srt_time(elapsed+c["a"])} --> {srt_time(elapsed+min(c["b"],d))}\n{content}')
        elapsed+=d
    (OUT/'中英字幕.srt').write_text('\n\n'.join(entries)+'\n',encoding='utf-8-sig')
    (WORK/'timeline.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2),encoding='utf-8')
    notes=f'''# 非常贝叶斯｜理论解析与实证实录

成片：{elapsed:.2f} 秒，1080×1920，9:16，30fps，H.264 / AAC。

以《非常贝叶斯.mp4》的中文解析为声音骨架，保留原声；穿插《clip_贝叶斯.mp4》的访谈画面、英文原声、原有字幕，另加清晰的中英字幕及解释。理论图解沿用纸张底色、橙青双色与逐句分析结构，并重新绘制。

## 论证结构

提问 → 比较样本有限 → 新信息推动判断与行动 → “Very Bayesian”评价 → 先验／似然／后验 → prior／posterior 原话与双关 → 据证据更新判断。

## 直接证据

- clip 00:01.95–00:04.60：Um, well, I don't have a huge comparison set.
- clip 00:52.30–00:58.70：Mark actually ingests new information and fully updates his worldview and then acts in accordance with the newly installed worldview.
- clip 00:58.70–01:04.73：Very Bayesian… I've never gotten such a nice compliment.
- clip 01:05.10–01:10.65：What lovely priors you have. / Yeah. Posterior.

以上是素材中的访谈陈述；概念图是理论说明，未将其作为统计实测。成片使用“原始访谈”标签，避免在重叠发言处错误分配说话人。

## 理论校正

先验不等于偏见；后验是结合证据后的判断；似然表示假设对新证据的解释程度。公式为 P(θ | D) ∝ P(D | θ) P(θ)。曲线仅作理论示意。删去了原解析将 posterior 称为“日常俚语”的句子，改用词义双关解释。

## 交付

- MP4 为带字幕成片，含中文解说与英文访谈原声。
- SRT 为可修改的双语字幕。
- 封面 JPG 与成片视觉一致。
- 制作文件位于 ../bayes_script_work/edit；重建脚本为 ../bayes_script_work/make_video.py。
'''
    (OUT/'剪辑说明.md').write_text(notes,encoding='utf-8')
    print('FINAL',str(final),f'{elapsed:.3f}s',flush=True)
