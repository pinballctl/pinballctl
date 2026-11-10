"""Millimetre-based layout model; NOT printable manufacturing geometry.
Run with project Python (Pillow required). Writes OBJ assemblies and scaled previews.
Component envelopes, hinge journals and clip positions are conceptual.
"""
from pathlib import Path
import math, json
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
MEDIA=ROOT.parent.parent/'media'
W,D,HF,HR,T=360.,280.,60.,90.,3.
BUTTONS=[('LOCK',35,190),('L RAMP',80,190),('SKILL',125,190),('ENTRY',170,190),('R ORBIT',215,190),('POP 1',80,135),('POP 2',125,145),('POP 3',170,135),('STANDUP',65,85),('SHOOTER',200,80),('DRAIN',130,40)]
HOLES=[(x,69+i*2.54) for i in range(63) for x in [285+j*2.54 for j in range(5)]+[302+j*2.54 for j in range(5)]]+[(x,70+i*3.1) for i in range(50) for x in [277,280,324,327]]
def height(y): return HF+(HR-HF)*y/D
COL={'base':'#384653','lid':'#536472','ring':'#5ce0ce','button':'#c6cfd4','board':'#ecede8','pcb':'#327761','amber':'#ffb638','hinge':'#be8bf0','clip':'#e38f61','dark':'#182b3b'}
def scene(angle):
 faces=[]
 def move(p,lid):
  x,y,z=p
  if lid:
   a=math.radians(-angle); y,z=y-D,z-HR
   y,z=y*math.cos(a)-z*math.sin(a),y*math.sin(a)+z*math.cos(a)
   y+=D;z+=HR
  return x,y,z
 def face(points,color,lid=False): faces.append(([move(p,lid) for p in points],color))
 def box(x,y,z,w,d,h,c,lid=False):
  p=[(x,y,z),(x+w,y,z),(x+w,y+d,z),(x,y+d,z),(x,y,z+h),(x+w,y,z+h),(x+w,y+d,z+h),(x,y+d,z+h)]
  if lid: p=[(px,py,pz+(HR-HF)*(py-y)/D) for px,py,pz in p]
  for ids in [(0,3,2,1),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]:face([p[i] for i in ids],c,lid)
 def cyl(x,y,z,r,h,c,lid=False,axis='z',n=24):
  ends=[]
  for v in [0,h]:
   ends.append([(x+(v if axis=='x' else r*math.cos(i*2*math.pi/n)),y+(v if axis=='y' else r*math.sin(i*2*math.pi/n)),z+(v if axis=='z' else r*(math.sin(i*2*math.pi/n) if axis=='y' else math.cos(i*2*math.pi/n)))) for i in range(n)])
  face(ends[0][::-1],c,lid);face(ends[1],c,lid)
  for i in range(n):j=(i+1)%n;face([ends[0][i],ends[0][j],ends[1][j],ends[1][i]],c,lid)
 box(0,0,0,W,D,3,COL['base'])
 box(0,0,3,W,3,HF-6,COL['base']);box(0,D-3,3,W,3,HR-6,COL['base'])
 for x in [0,W-T]:
  for pts in [[(x,0,3),(x,D,3),(x,D,HR-T),(x,0,HF-T)],[(x+T,0,3),(x+T,D,3),(x+T,D,HR-T),(x+T,0,HF-T)],[(x,0,HF-T),(x,D,HR-T),(x+T,D,HR-T),(x+T,0,HF-T)]]:face(pts,COL['base'])
 # Lid top and edges, an envelope rather than a fabricated panel with cutouts.
 top=[(0,0,HF),(W,0,HF),(W,D,HR),(0,D,HR)]
 face(top,COL['lid'],True);face([(x,y,z-T) for x,y,z in top[::-1]],COL['lid'],True)
 for i in range(4):a,b=top[i],top[(i+1)%4];face([a,b,(b[0],b[1],b[2]-T),(a[0],a[1],a[2]-T)],COL['lid'],True)
 for label,x,y in BUTTONS:
  cyl(x,y,height(y)+1,15,2,COL['ring'],True);cyl(x,y,height(y)+3,9,3,COL['button'],True)
  cyl(x,y,height(y)-23,8,20,COL['dark'],True)
 # Full size breadboard exact XY envelope; 10mm height is an unverified allowance.
 box(274,65,height(65)+1,56,165,10,COL['board'],True)
 for xx in [279,289,302,315,325]:box(xx,68,height(68)+12,1,159,.2,'#adb5b7',True)
 for hx,hy in HOLES:
  face([(hx+dx,hy+dy,height(hy+dy)+11.1) for dx,dy in [(-.35,-.35),(.35,-.35),(.35,.35),(-.35,.35)]],COL['dark'],True)
 box(150,225,height(225)+1,80,36,8,COL['dark'],True)
 box(156,231,height(231)+10,68,23,1,'#319ed5',True)
 for x,y,w,c in [(20,265,320,'#6ecde4'),(265,48,83.33,'#b88cee'),(265,20,41.67,'#68d6aa')]:box(x,y,height(y)+2,w,5,2,c,True)
 # Low, symmetric output lamps on top, near front-side flipper positions.
 for x in [19,341]:cyl(x,35,height(35)+2,4.1,3,COL['amber'],True)
 for x in [-5,360]:cyl(x,35,34,15,5,COL['ring'],axis='x');cyl(x-1,35,34,9,7,COL['button'],axis='x')
 for x in [105,155,205,255]:cyl(x,-5,30,15,5,COL['ring'],axis='y');cyl(x,-7,30,9,2,COL['button'],axis='y')
 # Candidate internal carrier and separate component envelopes, not routed PCB.
 box(65,85,12,180,110,2,COL['pcb'])
 box(80,135,14,80,40,15,COL['dark']);box(185,140,14,25.4,25.4,9.525,'#b69854')
 # Integrated pivot bosses and front latch positions; actual C sockets/strain pending.
 for x in [45,285]:
  cyl(x,280,90,5,30,COL['hinge'],axis='x')
  box(x,270,height(270)-3,30,10,5,COL['hinge'],True)
 for x in [65,280]:box(x,-2,46,15,3,11,COL['clip'])
 return faces

def obj(faces,path):
 with path.open('w') as f:
  f.write('# Units mm. Envelope model only. Not for fabrication.\n');n=1
  for points,c in faces:
   for x,y,z in points:f.write(f'v {x:.5f} {y:.5f} {z:.5f}\n')
   f.write('f '+' '.join(str(n+i) for i in range(len(points)))+'\n');n+=len(points)
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
def font(s):return ImageFont.truetype(FONT,s)
def render(draw,faces,area):
 def project(p):x,y,z=p;return .9*x+.5*y,.25*x-.45*y-.8*z
 coords=[project(p) for pts,c in faces for p in pts]; xs,ys=zip(*coords)
 x0,y0,x1,y1=area;scale=min((x1-x0)/(max(xs)-min(xs)),(y1-y0)/(max(ys)-min(ys)))
 def screen(p):u,v=project(p);return (x0+(u-min(xs))*scale,y0+(v-min(ys))*scale)
 # Orthographic z-buffer avoids large panels hiding nearer components.
 width,height=2200,1550
 depth={}
 for pts,c in faces:
  vertices=[(*screen(p),.5*p[0]-.9*p[1]+.8*p[2]) for p in pts]
  for j in range(1,len(vertices)-1):
   a,b,cpt=vertices[0],vertices[j],vertices[j+1]
   ax,ay,az=a;bx,by,bz=b;cx,cy,cz=cpt
   den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
   if abs(den)<1e-9:continue
   for yy in range(max(0,int(min(ay,by,cy))),min(height,int(max(ay,by,cy))+1)):
    for xx in range(max(0,int(min(ax,bx,cx))),min(width,int(max(ax,bx,cx))+1)):
     u=((by-cy)*(xx-cx)+(cx-bx)*(yy-cy))/den
     v=((cy-ay)*(xx-cx)+(ax-cx)*(yy-cy))/den
     w=1-u-v
     if min(u,v,w)<-1e-8:continue
     z=u*az+v*bz+w*cz;key=yy*width+xx
     if z>depth.get(key,-1e20):
      depth[key]=z;draw.point((xx,yy),fill=c)

def main():
 closed,opened=scene(0),scene(75)
 obj(closed,ROOT/'closed.obj');obj(opened,ROOT/'open-75deg.obj')
 im=Image.new('RGB',(2200,1550),'#f5f7fa');d=ImageDraw.Draw(im)
 def text(x,y,t,size=25,c='#243646'):d.text((x,y),t,font=font(size),fill=c)
 text(55,25,'TEST BENCH / SCALED GEOMETRY STUDY 01',42)
 text(55,85,'360 × 280 mm shell • front 60 / rear 90 mm • rear pivot • screw-free closure concept',27)
 text(55,145,'CLOSED',30);text(1140,145,'OPEN — 75° from closed',30)
 render(d,closed,(55,205,1030,710));render(d,opened,(1140,200,2145,735))
 text(55,745,'Purple: printed pivot positions    Orange tabs: front release clips',25)
 text(1140,745,'Green: carrier allowance • dark blocks: component envelopes',23)
 # Exact orthographic plan with uniform 2px/mm scale.
 ox,oy,k=90,880,2.
 def xy(x,y):return ox+k*x,oy+k*(D-y)
 d.rectangle([xy(0,D),xy(W,0)],fill=COL['lid'],outline='#243646',width=3)
 for name,x,y in BUTTONS:
  px,py=xy(x,y);d.ellipse((px-30,py-30,px+30,py+30),fill=COL['ring']);d.ellipse((px-18,py-18,px+18,py+18),fill=COL['button']);text(px-35,py+30,name,16,'#ffffff')
 a,b=xy(274,230),xy(330,65);d.rectangle([a,b],fill=COL['board']);text(a[0]+8,a[1]+110,'165',24);text(a[0]+8,a[1]+145,'× 56',24)
 for hx,hy in HOLES:
  px,py=xy(hx,hy);d.rectangle((px-.6,py-.6,px+.6,py+.6),fill='#667078')
 for x in [19,341]:px,py=xy(x,35);d.ellipse((px-9,py-9,px+9,py+9),fill=COL['amber'])
 for x in [-3,363]:px,py=xy(x,35);d.rectangle((px-5,py-30,px+5,py+30),fill=COL['ring'])
 d.rectangle([xy(150,261),xy(230,225)],fill='#319ed5')
 for x,y,w,c in [(20,265,320,'#6ecde4'),(265,48,83.33,'#b88cee'),(265,20,41.67,'#68d6aa')]:d.rectangle([xy(x,y+5),xy(x+w,y)],fill=c)
 text(90,835,'TOP PLAN — uniform scale, dimensions in mm',25)
 text(365,1450,'360 mm',25);text(820,1100,'280 mm',25)
 text(1000,865,'MODELLED SIZES & LOCATIONS',30)
 notes=['Breadboard: 165 × 56 mm (10 mm height allowance)', 'Breadboard width = 15.6% of the 360 mm enclosure', 'Button bezel Ø18 / diffused surround target Ø30', 'One RGB pixel per button; 17 pixels in one data chain', 'Amber flipper output lamps: x19 / x341, y35', 'Side flipper centres: y35, z34 (mirrored)', 'Main light strip: 320 mm; rear USB/DC layout pending', 'Hinge axis: y280, z90; pivot outside rear seam', 'Base/lid wall allowance: 3 mm; two front clips', '', 'MODEL STATUS: layout and motion envelopes only.', 'No screw holes or separate metal hinge proposed.', 'Snap sockets, stop/stay, wiring loop and latches need', 'detailed engineering and material-specific test prints.', 'Open lid must be supported; holding mechanism pending.']
 for i,line in enumerate(notes):text(1000,920+i*33,line,24)
 im.save(MEDIA/'test-bench-scaled-v1.png')
 (ROOT/'dimensions.json').write_text(json.dumps({'units':'mm','status':'layout-envelope-not-for-printing','width':W,'depth':D,'front_height':HF,'rear_height':HR,'wall_allowance':T,'breadboard':{'x':274,'y':65,'width':56,'length':165,'height_allowance':10},'hinge_axis_yz':[280,90],'open_angle_degrees':75,'output_lamp_centres_xy':[[19,35],[341,35]],'buttons_xy':BUTTONS},indent=2)+'\n')
 assert 274+56<W and 65+165<D
 assert all(math.hypot(x-a,y-b)>=40 for i,(_,x,y) in enumerate(BUTTONS) for _,a,b in BUTTONS[i+1:])
 print('Generated open/closed OBJ and scaled PNG; bounds and button spacing checks passed.')
if __name__=='__main__':main()
