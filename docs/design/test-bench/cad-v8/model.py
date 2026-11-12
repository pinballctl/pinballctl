"""Revision-8 visual reconstruction in solid CAD. All renders use these parts.
Dimensions inferred from the approved image unless stated in the accompanying README.
Not a supplier-certified component model or manufacturing release.
"""
from pathlib import Path
import sys, json, math
import cadquery as cq
ROOT=Path(__file__).resolve().parent
sys.path.append(str(ROOT.parent/'mechanical-v2'))
import design as joints
S=30/280
DARK=(.14,.155,.17); BLACK=(.025,.03,.035); TEAL=(.12,.85,.77)
METAL=(.64,.68,.71); ORANGE=(1,.34,.025); WHITE=(.88,.87,.81)
parts=[]
def add(name,shape,color=DARK,lid=False,kind='custom'):
 parts.append(dict(name=name,shape=shape,color=color,lid=lid,kind=kind));return shape

def box(x,y,z,w,d,h):return cq.Workplane('XY').box(w,d,h,centered=False).translate((x,y,z))
def roundbox(x,y,z,w,d,h,r):return box(x,y,z,w,d,h).edges('|Z').fillet(r)
def slab(z0,z1):return cq.Workplane('YZ').polyline([(0,z0),(280,z0+30),(280,z1+30),(0,z1)]).close().extrude(360)
def top(x,y):return cq.Workplane(cq.Plane(origin=(x,y,60+S*y),xDir=(1,0,0),normal=(0,-S,1)))
def topbox(x,y,w,d,h,z=0,r=0):
 q=top(x,y).workplane(offset=z).rect(w,d).extrude(h)
 if r:q=q.edges(cq.selectors.ParallelDirSelector(cq.Vector(0,-S,1))).fillet(r)
 return q

def topcircle(x,y,r,h,z=0,inner=None):
 q=top(x,y).workplane(offset=z).circle(r)
 if inner:q=q.circle(inner)
 return q.extrude(h)
def label(text,x,y,size=3,color=WHITE):
 add('label_'+text.replace(' ','_'),top(x,y).workplane(offset=.14).text(text,size*1.3,.16,font='Arial',halign='center',valign='center'),color,True,'marking')
def frontcircle(x,z,r,h,offset=0,inner=None):
 q=cq.Workplane(cq.Plane(origin=(x,-offset,z),xDir=(1,0,0),normal=(0,-1,0))).circle(r)
 if inner:q=q.circle(inner)
 return q.extrude(h)
def sidecircle(y,z,r,h,side=360,inner=None):
 q=cq.Workplane(cq.Plane(origin=(side,y,z),xDir=(0,1,0),normal=(1 if side else -1,0,0))).circle(r)
 if inner:q=q.circle(inner)
 return q.extrude(h)

def build():
 parts.clear()
 outer=roundbox(0,0,0,360,280,100,16).intersect(joints.yz([(0,0),(280,0),(280,83.6),(0,53.6)],0,360))
 # Rounded floor edge and continuous 3mm side walls.
 outer=outer.edges('<Z').fillet(3)
 inner=roundbox(3,3,3,354,274,110,13)
 base=outer.cut(inner)
 lid=roundbox(0,0,0,360,280,110,16).intersect(slab(54,60))
 # Soft exterior top edge, six-mm lid skin before component pockets.
 class TopRim(cq.Selector):
  def filter(self,objects):
   return [e for e in objects if all(abs(v.Z-60-S*v.Y)<1e-5 for v in e.Vertices())]
 lid=lid.edges(TopRim()).fillet(2.2)
 for x in joints.CLIPS:
  base=base.cut(box(x-1,-1,28,16,5,30)).union(joints.latch_base(x))
  lid=lid.union(joints.latch_lid(x))
  # Underside pocket clears the existing clip arm in the thicker reference lid.
  lid=lid.cut(box(x-.4,-.4,53.6,14.8,2.6,1.8))
  add('clip_face_'+str(x),roundbox(x+1,-2.9,46,12,3,6,.6),ORANGE)
 # Compact rear snap-pivot study matching the reference silhouette.
 for x in joints.HINGES:
  cheeks=[]
  for xx in [x,x+28]:
   stem=box(xx,277,80,3,6,11)
   eye=joints.pin(xx,282,91,5,3).cut(joints.pin(xx-.2,282,91,3.3,3.4))
   cheeks.append(stem.union(eye).cut(joints.pin(xx-.2,282,91,3.3,3.4)))
  fixed=cheeks[0].union(cheeks[1]).union(box(x,277,80,31,3,4))
  base=base.union(fixed)
  arms=box(x+5,267,89,2,15,4).union(box(x+24,267,89,2,15,4))
  root=box(x+4,267,85,23,6,5)
  moving=arms.union(root).union(joints.pin(x+1,282,91,3,6)).union(joints.pin(x+24,282,91,3,6))
  lid=lid.union(moving)
  # Small separate cosmetic cap: an envelope, attachment design pending.
  add('hinge_cover_'+str(x),roundbox(x+7,276,93,17,9,2.5,2),(.4,.18,.65),True,'component-envelope')
  lid=lid.cut(fixed.union(fixed.translate((0,0,.4))))
 # Ports and fixed buttons.
 for i,x in enumerate([86,140,194,248]):
  base=base.cut(frontcircle(x,28,8.2,8,offset=-5))
  add('front_diffuser_'+str(i),frontcircle(x,28,10.3,1,inner=8),TEAL)
  add('front_bezel_'+str(i),frontcircle(x,28,9,1.2,offset=1,inner=7.3),METAL)
  add('front_actuator_'+str(i),frontcircle(x,28,7,1.3,offset=1),METAL)
  add('front_body_'+str(i),frontcircle(x,28,8,20,offset=-23),BLACK,kind='component-envelope')
  name=['START','LAUNCH','SELECT','ADD PLAYER'][i]
  q=cq.Workplane(cq.Plane(origin=(x,-.2,12),xDir=(1,0,0),normal=(0,-1,0)))
  add('front_label_'+str(i),q.text(name,4.5,.18,font='Arial'),WHITE,kind='marking')
 for side in [0,360]:
  base=base.cut(sidecircle(35,30,8.2,-6,side))
  add('flipper_diffuser_'+str(side),sidecircle(35,30,10.3,1,side,8),TEAL)
  add('flipper_bezel_'+str(side),sidecircle(35,30,9,2,side,7.3),METAL)
  add('flipper_actuator_'+str(side),sidecircle(35,30,7,2.1,side),METAL)
 for name,y,r in [('12V IN',210,4),('USB',172,6)]:
  base=base.cut(sidecircle(y,40,r,-6))
  add(name+'_flange',sidecircle(y,40,r+3,1.1,inner=r),BLACK)
  if name=='USB':
   # USB-C requirement from photo; the image's Micro-B is not reused.
   q=cq.Workplane(cq.Plane(origin=(361.2,y,40),xDir=(0,1,0),normal=(1,0,0)))
   add('usb_c_lip',q.rect(8.7,3.2).rect(7.5,2).extrude(.5),METAL,kind='component-envelope')
  else:add('dc_centre_pin',sidecircle(y,40,1,1.4),METAL)
  q=cq.Workplane(cq.Plane(origin=(360.2,y-17,40),xDir=(0,1,0),normal=(1,0,0)))
  add(name+'_label',q.text(name,3.2,.15,font='Arial'),WHITE,kind='marking')
 # Breadboard oriented across the case, matching the approved image.
 bx,by=285,118
 lid=lid.cut(topbox(bx,by,87,60,-20,r=3))
 tray=topbox(bx,by,92,65,-13,r=5).cut(topbox(bx,by,85,58,-10,r=2))
 lid=lid.union(tray)
 board=topbox(bx,by,83,56,9.7,z=-8.7,r=1)
 pts=[]
 for i in range(30):
  for j in range(10):pts.append((-36.83+i*2.54,-13.97+j*2.54+(5.08 if j>=5 else 0)))
 for i in range(25):
  for y in [-23,-20.46,20.46,23]:pts.append((-30.48+i*2.54,y))
 holes=top(bx,by).workplane(offset=-1.1).pushPoints(pts).circle(.52).extrude(2.2)
 board=board.cut(holes)
 add('breadboard_400_holes',board,WHITE,True,'component-envelope')
 for y in [-25,25]:
  add('breadboard_red_'+str(y),topbox(bx,by+y,76,.25,.08,z=1.05),( .85,.15,.1),True,'marking')
  add('breadboard_blue_'+str(y),topbox(bx,by+y-1.1,76,.25,.08,z=1.05),(.1,.3,.75),True,'marking')
 # Display: real glass window, bezel, PCB envelope, text.
 lid=lid.cut(topbox(185,233,70,25,-12))
 add('lcd_bezel',topbox(185,233,83,36,1.5,r=2).cut(topbox(185,233,70,25,3)),BLACK,True)
 add('lcd_glass',topbox(185,233,69,24,.6,z=.3),(.025,.10,.8),True)
 add('lcd_pcb',topbox(185,233,80,36,1.6,z=-17),(.03,.28,.12),True,'component-envelope')
 for txt,y in [('PINBALL CTL',237),('TEST BENCH',229)]:
  add('lcd_'+txt,top(185,y).workplane(offset=1).text(txt,6.4,.08,font='Courier New'),(.65,.9,1),True,'marking')
 # Actual-style controls with separate diffusers and underside envelopes.
 for name,x,y in [('LOCK',43,194),('L RAMP',84,194),('ENTRY',166,194),('R ORBIT',207,194),('SHOOTER',195,76)]:
  lid=lid.cut(topbox(x,y,10,9,-15))
  add(name+'_diffuser',topbox(x,y,19,12,.8,r=1),TEAL,True)
  body=topbox(x,y,12.8,5.8,6.5,z=.8)
  for dx in [-3.25,3.25]:
   q=cq.Workplane(cq.Plane(origin=(x+dx,y-4,64+S*y),xDir=(1,0,0),normal=(0,1,0))).circle(1).extrude(8)
   body=body.cut(q)
  add(name+'_body',body,BLACK,True,'component-envelope')
  lever=topbox(x+1,y,14,2.5,.4,z=8).rotate((x-6,y,68+S*y),(x-6,y+1,68+S*y),-12)
  add(name+'_lever',lever,METAL,True,'component-envelope')
  for dx in [-4,0,4]:add(name+'_terminal_'+str(dx),topbox(x+dx,y,1,.5,-7,z=-6),METAL,True,'component-envelope')
  label(name,x,y-12,3.5)
 for name,x,y,color in [('SKILL',125,194,(.03,.65,.25)),('STANDUP',60,78,(.85,.04,.05))]:
  lid=lid.cut(topcircle(x,y,8.2,-15))
  add(name+'_diffuser',topbox(x,y,27,21,.8,r=1),TEAL,True)
  add(name+'_bezel',topbox(x,y,24,18,2,z=.8,r=1),BLACK,True,'component-envelope')
  add(name+'_cap',topbox(x,y,20,14,2,z=2.8,r=.5),color,True,'component-envelope')
  add(name+'_tail',topcircle(x,y,8,-35,z=-1),BLACK,True,'component-envelope')
  label(name,x,y-15,3.5)
 for i,(x,y) in enumerate([(70,137),(120,137),(170,137)],1):
  lid=lid.cut(topcircle(x,y,12.2,-15))
  # Local underside counterbore leaves 2mm panel plus 1mm diffuser at snap tabs.
  lid=lid.cut(topcircle(x,y,15.6,4,z=-6))
  add('pop_diffuser_'+str(i),topcircle(x,y,15.5,1,inner=12),TEAL,True)
  add('pop_bezel_'+str(i),topcircle(x,y,13.6,2,z=1,inner=11.8),ORANGE,True,'component-envelope')
  add('pop_cap_'+str(i),topcircle(x,y,11.5,2.3,z=1),ORANGE,True,'component-envelope')
  add('pop_tail_'+str(i),topcircle(x,y,11,-29,z=-1),BLACK,True,'component-envelope')
  label('POP '+str(i),x,y-20,3.6)
 lid=lid.cut(topcircle(126,66,8.2,-15))
 add('drain_diffuser',topcircle(126,66,10.3,1,inner=8),TEAL,True)
 add('drain_bezel',topcircle(126,66,9,1.2,z=1,inner=7.3),METAL,True)
 add('drain_cap',topcircle(126,66,7,1.3,z=1),METAL,True)
 add('drain_tail',topcircle(126,66,8,-20),BLACK,True,'component-envelope');label('DRAIN',126,51,3.5)
 # Main and secondary strip diffusers, retaining individual visible pixel lenses.
 for name,x,y,w,n,color in [('main',180,258,320,46,TEAL),('short',270,47,47,12,(.52,.22,1)),('status',315,47,24,6,TEAL)]:
  lid=lid.cut(topbox(x,y,w+2,5,-2,r=1))
  add(name+'_strip_back',topbox(x,y,w,4,.8,z=-.8,r=.5),(.05,.35,.32) if name=='main' else BLACK,True)
  for i in range(n):add(name+'_pixel_'+str(i),topbox(x-w/2+(i+.5)*w/n,y,w/n*.65,2.6,.5,z=.1),color,True,'component-envelope')
 for x in [25,337]:
  lid=lid.cut(topcircle(x,42,4.2,-10))
  add('amber_bezel_'+str(x),topcircle(x,42,5,1,inner=3.6),METAL,True)
  add('amber_lens_'+str(x),topcircle(x,42,3.5,1.7),(1,.48,.02),True)
 # Fine recessed panel outlines matching the reference's labelled connector bays.
 for px,py,pw,pd in [(264,205,38,28),(311,207,29,42),(264,77,43,21),(314,77,39,21)]:
  groove=topbox(px,py,pw,pd,-.3,r=2).cut(topbox(px,py,pw-.6,pd-.6,-.5,r=1.7))
  lid=lid.cut(groove)
 # Female sockets: recessed apertures and actual contact openings.
 for name,x,y,n in [('EXPANSION',264,201,12),('3.3V  GND',264,75,6),('5V  GND',314,75,6)]:
  rows=2 if n==12 else 1;cols=n//rows;w=cols*2.54+3;depth=rows*2.54+3
  lid=lid.cut(topbox(x,y,w,depth,-10))
  housing=topbox(x,y,w,depth,3,z=-1)
  for i in range(cols):
   for j in range(rows):housing=housing.cut(topbox(x+(i-(cols-1)/2)*2.54,y+(j-(rows-1)/2)*2.54,1.1,1.1,-3,z=2.1))
  add(name+'_socket',housing,BLACK,True,'component-envelope');label(name,x,y+10,3.3)
 lid=lid.cut(topbox(311,201,12,19,-12))
 add('power_bezel',topbox(311,201,16,23,1,r=2),BLACK,True)
 add('power_rocker',topbox(311,201,11,17,3,z=1,r=1),DARK,True,'component-envelope');label('PROTO',311,226,3.2);label('POWER',311,220,3.2)
 # Rubber feet are separate purchased-part envelopes.
 for x in [23,337]:
  for y in [23,257]:add('foot_'+str(x)+'_'+str(y),cq.Workplane('XY').center(x,y).circle(8).extrude(-2),BLACK,kind='component-envelope')
 add('base_shell',base,DARK);add('lid_shell',lid,(.17,.185,.20),True)
 return parts

def transformed(p,angle):
 return p['shape'].rotate((0,282,91),(1,282,91),-angle) if p['lid'] else p['shape']

def main():
 build();report=[]
 for p in parts:
  valid=all(v.isValid() for v in p['shape'].vals());assert valid,p['name']
  report.append({k:p[k] for k in ['name','lid','kind']})
 for angle in [0,75]:
  a=cq.Assembly()
  for p in parts:a.add(transformed(p,angle),name=p['name'].replace(' ','_'),color=cq.Color(*p['color']))
  a.export(str(ROOT/('assembly-closed.step' if angle==0 else 'assembly-open.step')))
 for name in ['base_shell','lid_shell']:
  q=next(p['shape'] for p in parts if p['name']==name)
  cq.exporters.export(q,str(ROOT/(name+'.step')))
  cq.exporters.export(q,str(ROOT/(name+'.stl')),tolerance=.08,angularTolerance=.15)
 (ROOT/'parts.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Exported',len(parts),'named CAD parts; valid shapes. Fit/motion/manufacturing validation pending.')
if __name__=='__main__':main()
