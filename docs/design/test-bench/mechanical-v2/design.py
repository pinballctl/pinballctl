"""CadQuery 2.8 prototype mechanics, mm. Run in isolated CAD environment.
Not a manufacturing release: coupon fit, fatigue and loaded lid tests required.
"""
from pathlib import Path
import json, math
import cadquery as cq
OUT=Path(__file__).resolve().parent
W,D=360,280
AY,AZ=286,94
HINGES=[48,278]
CLIPS=[65,280]

def box(x,y,z,w,d,h):return cq.Workplane('XY').box(w,d,h,centered=False).translate((x,y,z))
def yz(points,x,width):return cq.Workplane('YZ').polyline(points).close().extrude(width).translate((x,0,0))
def pin(x,y,z,r,length):return cq.Workplane('YZ').center(y,z).circle(r).extrude(length).translate((x,0,0))
def union(items):
 r=items[0]
 for item in items[1:]:r=r.union(item)
 return r

def hinge(x, clearance=.3):
 # Fixed bearing cheeks connect to rear shell through a lower bridge.
 cheeks=union([box(x,282,82,4,10,19),box(x+30,282,82,4,10,19),box(x,277,82,34,15,3.5)])
 for px in [x-1,x+29]:cheeks=cheeks.cut(pin(px,AY,AZ,3+clearance,6))
 # Two opposed axial-snap arms, squeezed toward each other during installation.
 arms=[]
 for ax in [x+6,x+26]:
  root=box(ax-2,253,86,6,7,10)
  beam=box(ax,258,92,2,28,4)
  # Rounded root transition in the flex plane; integrated into root/arm.
  blend=cq.Workplane('XY').center(ax+1,259).circle(2).extrude(4).translate((0,0,92))
  arms.extend([root,beam,blend])
 left=pin(x+1.8,AY,AZ,3,5.2).edges('<X').chamfer(.5)
 right=pin(x+27,AY,AZ,3,5.2).edges('>X').chamfer(.5)
 moving=union(arms+[left,right,box(x+4,253,86,26,6,3),box(x+14,270,87,6,9,8),box(x+14,258,87,6,21,3)])
 # Integral travel stop: sector just beyond the 75-degree service position.
 sector=[(AY+r*math.cos(math.radians(a)),AZ+r*math.sin(math.radians(a))) for r,angles in [(9,range(88,96)),(18,range(95,87,-1))] for a in angles]
 stop=yz(sector,x+14,6)
 cheeks=union([cheeks,stop,box(x+14,291.5,84,6,3.5,29),box(x+14,284,110,6,11,3)])
 return cheeks,moving

def latch_base(x):
 # Bottom-rooted arm, 27mm nominal free length, bends inward (+Y).
 beam=box(x,0,28,14,1.8,27)
 hook=yz([(0,52),(-1.4,52),(-1.4,53),(0,55)],x,14)
 pad=box(x+2,-.5,46,10,.5,4)
 root=box(x-1,0,25,16,3,4)
 # Radius fillet at the inner root, rounded in YZ.
 blend=pin(x,.9,28,.9,14)
 r=union([beam,hook,pad,root,blend])
 return r.edges(cq.selectors.BoxSelector((x-.01,1.79,28.99),(x+14.01,1.81,29.01))).fillet(.6)

def latch_lid(x):
 # External receiver skirt; catch window leaves zero static beam deflection.
 skirt=box(x-3,-2.6,48,20,2,12)
 window=box(x-.4,-3,51.6,14.8,3,4)
 bridge=box(x-3,-2.6,58,20,6,2)
 return skirt.cut(window).union(bridge)

def build():
 outer=yz([(0,0),(280,0),(280,86.6),(0,56.6)],0,360)
 inner=yz([(3,3),(277,3),(277,100),(3,100)],3,354)
 base=outer.cut(inner)
 # 0.4mm vertical seam, top skin z57..60 at front and87..90 at rear.
 lid=yz([(0,57),(280,87),(280,90),(0,60)],0,360)
 for x in CLIPS:
  base=base.cut(box(x-1,-1,28,16,5,30)).union(latch_base(x))
  lid=lid.union(latch_lid(x))
 for x in HINGES:
  fixed,moving=hinge(x);base=base.union(fixed);lid=lid.union(moving)
 # Recessed half-size breadboard: 83x56 candidate, height 9.7mm allowance.
 # Pocket 84x57, top working surface intended 1mm proud; shim/sample required.
 def tray_poly(y0,y1,below,above):
  return [(y0,60+30*y0/280-below),(y1,60+30*y1/280-below),(y1,60+30*y1/280+above),(y0,60+30*y0/280+above)]
 lid=lid.union(yz(tray_poly(96.5,186.5,11.7,0),268.5,63))
 lid=lid.cut(yz(tray_poly(99.5,183.5,8.7,20),271.5,57))
 # Expansion header and rail socket windows: provisional connector allowances.
 for x,y,w,depth in [(265,204,34,8),(265,73,58,8)]:
  lid=lid.cut(box(x,y,0,w,depth,120))
 # Different controls: commercial round holes and custom microswitch paddle slots.

 positions=[(65,85,8),(125,190,8),(80,135,12),(125,145,12),(170,135,12),(130,40,8)]
 for x,y in [(35,190),(80,190),(170,190),(215,190),(200,80)]:
  lid=lid.cut(box(x-5,y-9,0,10,18,120))
 for x,y,r in positions:
  lid=lid.cut(cq.Workplane('XY').center(x,y).circle(r+.2).extrude(120))
 for x in [19,341]:lid=lid.cut(cq.Workplane('XY').center(x,35).circle(4.2).extrude(120))
 for x in [105,155,205,255]:base=base.cut(cq.Workplane('XZ').center(x,30).circle(8.2).extrude(6,both=True))
 for x in [0,357]:base=base.cut(pin(x-1,35,34,8.2,5))
 # Right-side service ports: candidate circular openings, final USB bore pending sample.
 base=base.cut(pin(356,190,40,4,8)).cut(pin(356,230,40,12,8))
 return base,lid

def export(part,name):
 if 'coupon' in name:
  bb=part.val().BoundingBox();part=part.translate((-bb.xmin,-bb.ymin,-bb.zmin))
 assert part.val().isValid(),name+' invalid BREP'
 assert len(part.solids().vals())==1,(name,len(part.solids().vals()))
 cq.exporters.export(part,str(OUT/(name+'.step')))
 cq.exporters.export(part,str(OUT/(name+'.stl')),tolerance=.06,angularTolerance=.15)

def main():
 base,lid=build();export(base,'base-prototype');export(lid,'lid-prototype')
 # Small coupons use identical joint geometry; no new tolerances hidden in samples.
 fixed,moving=hinge(0)
 export(fixed.translate((0,-253,-84)),'hinge-fixed-coupon')
 export(moving.translate((0,-253,-84)),'hinge-moving-coupon')
 support=box(-3,0,25,20,3,33).cut(box(-1,-1,28,16,5,30)).union(latch_base(0))
 export(support.translate((3,3,-25)),'latch-base-coupon')
 export(latch_lid(0).translate((3,3,-25)),'latch-lid-coupon')
 # At closed state catches sit inside their windows. Initial lift requires release.
 overlaps=[]
 for angle in [0,.25,.5,1,2,3,5,10,15,30,45,60,75,78,79,80,85,90]:
  moved=lid.rotate((0,AY,AZ),(1,AY,AZ),-angle)
  vol=base.intersect(moved).val().Volume()
  overlaps.append({'angle_deg':angle,'intersection_mm3':round(vol,6)})
 released=base
 for x in CLIPS:released=released.cut(box(x-1,-3,29,16,7,29))
 free_sweep=[]
 for angle in [i*.5 for i in range(151)]:
  vol=released.intersect(lid.rotate((0,AY,AZ),(1,AY,AZ),-angle)).val().Volume()
  free_sweep.append(vol)
 assert max(free_sweep)<1e-5,('Released sweep interference',max(free_sweep))
 assert overlaps[0]['intersection_mm3']<1e-5,'Closed interference'
 # Released check excludes flexible arms instead of pretending to simulate their deformation.
 asm=cq.Assembly();asm.add(base,name='base',color=cq.Color(.14,.18,.22));asm.add(lid,name='lid',color=cq.Color(.22,.29,.33));asm.export(str(OUT/'assembly-closed.step'))
 report={'status':'prototype-not-manufacturing-release','cadquery':cq.__version__,'axis_yz_mm':[AY,AZ],'shell_mm':[360,280,60,90],'breadboard_mm':[56,83],'breadboard_height_allowance_mm':9.7,'pocket_xy_mm':[57,84],'pocket_depth_below_top_mm':8.7,'pin_diameter_mm':6,'bore_diameter_mm':6.6,'radial_clearance_mm':.3,'hinge_arm_free_length_mm':26,'hinge_arm_thickness_mm':2,'hinge_arm_assembly_deflection_mm':2.6,'hinge_beam_estimated_strain':1.5*2*2.6/26**2,'clip_length_mm':27,'clip_thickness_mm':1.8,'clip_release_travel_mm':1.6,'clip_beam_estimated_strain':1.5*1.8*1.6/27**2,'full_assembly_rigid_sweep':overlaps,'released_sweep_max_intersection_mm3':max(free_sweep),'released_sweep_step_deg':.5,'released_sweep_limit_deg':75,'notes':['Beam estimates are screening only, not material allowable or fatigue validation.','Rigid latch interference during initial opening is expected until both clips are pressed inward.','Released sweep excludes front flexible clip bodies; it does not simulate their deformation.','Integral stop is intended to contact beyond 75 degrees; not a lid stay.','Full housing component inserts, cable loop and lid stay remain pending.']}
 (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
