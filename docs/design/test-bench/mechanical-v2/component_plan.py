"""Reproducible component-clearance plan; Pillow only. Dimensions are mm."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json
P=Path(__file__).resolve().parent
parts=json.loads((P/'components.json').read_text())
im=Image.new('RGB',(1900,1450),'#f3f6f8');d=ImageDraw.Draw(im)
f='/System/Library/Fonts/Supplemental/Arial.ttf'
def text(x,y,t,size=23,c='#203746'):d.text((x,y),t,font=ImageFont.truetype(f,size),fill=c)
k=2.6;ox=75;oy=230
xy=lambda x,y:(ox+x*k,oy+(280-y)*k)
def rect(x,y,w,h,fill,outline=None):d.rectangle([xy(x,y+h),xy(x+w,y)],fill=fill,outline=outline,width=2)
def circle(x,y,r,fill):a,b=xy(x,y);d.ellipse((a-r*k,b-r*k,a+r*k,b+r*k),fill=fill)
text(65,35,'COMPONENT FIT STUDY / RECESSED HALF-SIZE BREADBOARD',36)
text(65,95,'360 × 280 mm shell retained • actual part sizes + explicitly marked custom allowances',25)
rect(0,0,360,280,'#324652');rect(20,263,320,14,'#61cbc8');rect(140,215,90,45,'#1c2831');text(*xy(147,242),'LCD allowance',20,'#dce9ed')
for name,x,y in [('LOCK',35,190),('L RAMP',80,190),('ENTRY',170,190),('R ORBIT',215,190),('SHOOTER',200,80)]:
 rect(x-15,y-17,30,34,'#64cdbb');rect(x-6.4,y-3.25,12.8,6.5,'#172b33');rect(x-5,y-1,10.8,2,'#c4ccd0');text(xy(x-16,y-21)[0],xy(x-16,y-21)[1],name,16,'#ffffff')
for n,x,y in [('1',80,135),('2',125,145),('3',170,135)]:circle(x,y,17,'#e3bb62');circle(x,y,13.6,'#ed8d28');text(*xy(x-10,y+5),'POP '+n,17)
rect(50,72,30,26,'#64cdbb');rect(53,76,24,18,'#b44942');text(*xy(48,64),'STANDUP',17,'#ffffff')
rect(110,177,30,26,'#64cdbb');rect(113,181,24,18,'#7aaf8d');text(*xy(108,169),'SKILL',17,'#ffffff')
circle(130,40,15,'#64cdbb');circle(130,40,9,'#b9c4c9');text(*xy(114,20),'DRAIN',17,'#ffffff')
for x in [19,341]:circle(x,35,4.1,'#ffb638')
# Actual 56x83 breadboard inside57x84 cutout.
rect(271.5,99.5,57,84,'#152b36');rect(272,100,56,83,'#eeeae3')
for i in range(30):
 for xx in list(range(10)):
  x=281+(xx+(2 if xx>=5 else 0))*2.54;y=103+i*2.54;a,b=xy(x,y);d.ellipse((a-1,b-1,a+1,b+1),fill='#455661')
for i in range(25):
 for x in [275,277.5,323,325.5]:a,b=xy(x,104+i*3.05);d.ellipse((a-1,b-1,a+1,b+1),fill='#455661')
text(*xy(271,96),'83 × 56 mm',19,'#ffffff')
rect(265,204,34,8,'#131d24');text(*xy(260,221),'EXPANSION',16,'#ffffff')
rect(265,73,58,8,'#131d24');text(*xy(262,68),'3.3V GND  5V GND',15,'#ffffff')
rect(265,230,18,10,'#131d24');text(*xy(260,249),'PWR',15,'#ffffff')
rect(265,45,83.33,12,'#a47fe0');rect(265,20,41.67,12,'#62cba5')
for x in [-3,363]:a,b=xy(x,35);d.rectangle((a-4,b-39,a+4,b+39),fill='#64cdbb')
text(430,990,'360 mm',27);text(75,1030,'RIGHT SIDE: 12V input y190 / USB y230 / z40 mm',23);text(1025,550,'280',24);text(1025,580,'mm',21)
text(1120,230,'REAL PARTS',28)
lines=['3 × Sanwa OBSF-24 orange bumpers','Ø24 cutout / Ø27.2 bezel','34 mm custom RGB surround allowance','45 mm depth with terminals + wire space','','5 × D2F-01L lever switches','12.8 × 5.8 × 6.5 mm body','Actual metal levers; 30 × 34 mm mount bay','25 mm below-panel service allowance','','Skill + standup: 24 × 18 mm faces','Ø16 mounting / 50 mm depth allowance','','7 × Ø16 round controls','Ø18 bezel / 35 mm depth allowance','','Half-size breadboard: 83 × 56 mm','Pocket: 84 × 57 mm, depth 8.7 mm*','*9.7 mm height assumption; sample required','','Expansion / power connectors: reserved','Exact SKU, pinout and current limits pending']
for i,t in enumerate(lines):text(1120,280+30*i,t,22)
text(75,1080,'BREADBOARD SECTION — enlarged, vertical dimensions in mm',26)
# 10x section, panel surface baseline1240
basey=1270; x=120;ss=10
# 56mm board width plus tray
# horizontal panel either side
for a,b in [(x-60,x-5),(x+565,x+630)]:d.rectangle((a,basey,b,basey+30),fill='#324652')
d.rectangle((x-5,basey+87,x+565,basey+117),fill='#324652')
for a in [x-35,x+565]:d.rectangle((a,basey,a+30,basey+117),fill='#324652')
d.rectangle((x,basey-10,x+560,basey+87),fill='#eeeae3',outline='#344952',width=2)
text(780,1160,'Top sits ~1 mm proud',24);text(780,1200,'8.7 mm pocket + 3 mm floor',24);text(780,1240,'Adjust depth using measured board height.',23)
text(75,1410,'Proposed carrier/diffuser envelopes are not supplier dimensions. No PCB power circuit or expansion pin mapping is released.',21)
im.save(P.parents[2]/'media/test-bench-component-plan-v2.png')
# Basic independent clearance checks for the proposed panel envelopes.
items=[(272,100,56,83),(265,204,34,8),(265,73,58,8),(315,222,24,18),(140,215,90,45)]
assert all(x>=0 and y>=0 and x+w<=360 and y+h<=280 for x,y,w,h in items)
for i,(x,y,w,h) in enumerate(items):
 for a,b,c,e in items[i+1:]:assert x+w<=a or a+c<=x or y+h<=b or b+e<=y
print('Component plan generated; selected bay bounds and overlaps checked.')
