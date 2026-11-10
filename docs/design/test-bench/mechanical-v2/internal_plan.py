"""Draw proposed internal placement envelopes, not a routed PCB or motion proof."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
P=Path(__file__).resolve().parent
s=json.loads((P/'internal-layout.json').read_text())
def overlap(a,b):
 x,y=a['xy'];w,h=a['size'];u,v=b['xy'];p,q=b['size']
 return x<u+p and x+w>u and y<v+q and y+h>v
for i,a in enumerate(s['modules']):
 for b in s['modules'][i+1:]+s['keepouts']:
  assert not overlap(a,b),(a['name'],b['name'])
im=Image.new('RGB',(1500,1150),'#edf2f5');d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Supplemental/Arial.ttf'
def label(x,y,t,size=22,color='#203746'):d.text((x,y),t,font=ImageFont.truetype(font,size),fill=color)
k=2.65; ox=65; oy=150
def rect(x,y,w,h,c):
 a=(ox+x*k,oy+(280-y-h)*k,ox+(x+w)*k,oy+(280-y)*k)
 d.rectangle(a,fill=c,outline='#405665',width=2);return a
label(65,30,'INTERNAL PLACEMENT / CLOSED-LID PLAN',34)
label(65,82,'360 × 280 mm shell • all module and wiring envelopes provisional',24)
rect(0,0,360,280,'#d5dee3')
a=rect(100,105,230,140,'#85b8a0');label(a[0]+10,a[3]-27,'Carrier PCB 230 × 140',22)
for i,m in enumerate(s['modules'],1):
 x,y=m['xy'];w,h=m['size'];a=rect(x,y,w,h,'#354f61');label(a[0]+7,a[1]+5,str(i),24,'white')
 assert x>=100 and y>=105 and x+w<=330 and y+h<=245
 label(1060,170+(i-1)*90,f'{i}. '+m['name'].replace(' envelope',''),17)
 label(1060,195+(i-1)*90,f'{w} × {h}; top z={m["top_z"]}',18)
for r in s['keepouts']:
 x,y=r['xy'];w,h=r['size'];a=rect(x,y,w,h,'#f1c888')
 for xx in range(int(a[0])+4,int(a[2]),10):d.line((xx,a[1],xx,a[3]),fill='#d69c45')
 if 'min_lid_z' in r:label(a[0]+3,a[1]+5,'TAIL',15)
rect(100,248,160,25,'#a49cbd');label(ox+105*k,oy+11*k,'Hinge harness corridor',18)
label(ox+90,oy+257*k,'Front button terminals / wiring',21)
label(1060,650,'Amber: keep clear',21)
label(1060,690,'Antenna left of ESP;',19)
label(1060,720,'USB at right rear.',19)
label(65,930,'Closed-height checks (nominal only)',26)
label(65,975,'Carrier top z=11.6; skill terminal envelope z≈26 → ≈14 mm above bare PCB.',22)
label(65,1015,'Buck top z=30; breadboard tray lowest z≈58.6 → ≈29 mm nominal clearance.',22)
label(65,1070,'No populated lid-sweep, thermal, antenna or wiring-clearance validation. Do not fabricate from this plan.',21)
im.save(P.parents[2]/'media/test-bench-internal-plan-v1.png')
print('Module rectangles fit carrier outline; other clearances remain provisional.')
