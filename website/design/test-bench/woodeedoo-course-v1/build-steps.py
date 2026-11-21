"""Dimensioned part-set diagrams and isometric assembly renders for the build guide.
Illustrative placement only: actual box fit, fixing details and slope need checking.
"""
from pathlib import Path
import html
import subprocess

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT.parents[2] / 'assets/docs/media'

SETS = [
 ('carrier','A / Carrier and retaining cleats',
  [('Carrier',370,370,6),('4 cleats',30,12,12)],
  [(0,0,0,370,370,6),(40,0,6,30,12,12),(300,0,6,30,12,12),(0,260,6,12,30,12),(358,260,6,12,30,12)],
  ['370 square is nominal; trim to the delivered cavity.','Cleat positions are illustrative; fix into pine walls.']),
 ('console','B / Removable console and U-frame',
  [('Top',240,240,6),('2 sides',240,83,12),('Rear',216,83,12)],
  [(0,0,0,12,240,83),(228,0,0,12,240,83),(12,0,0,216,12,83),(0,0,118,240,240,6)],
  ['Exploded top: lift off; do not glue it to the frame.','Front stays open. Holes, pads and cable passage pending.']),
 ('course','C / L-course, rails and end stops',
  [('Course blank',360,360,6),('Outer rear',317,30,12),('Outer left',305,30,12),('Inner rear',275,30,12),('Inner left',263,30,12),('2 stops',30,30,12)],
  [(10,10,0,360,100,6),(10,110,0,100,260,6),(33,33,6,317,12,30),(33,45,6,12,305,30),(75,75,6,275,12,30),(75,87,6,12,263,30),(45,350,6,30,12,30),(350,45,6,12,30,30)],
  ['Remove the front-right 260 square from the blank.','Render is level for clarity; final course is sloped.']),
 ('supports','D / Adjustable course supports and sensor pads',
  [('6+ course pads',30,30,12),('Shim layers',30,30,6),('Sensor pads','fit','fit','6 / 12')],
  [(0,0,0,30,30,12),(0,0,12,30,30,6),(0,0,25,30,30,6),(85,0,0,30,30,12),(85,0,12,30,30,6),(85,0,25,30,30,6)],
  ['Exploded layer examples, not prescribed final heights.','Sensor-pad footprint and lens height come from the parts.']),
 ('gate','E / Manual gate and removable trough cover',
  [('Gate',29,40,6),('4 guide cheeks',12,40,'6 / 12'),('Cover',110,54,6),('Keeper',29,12,12)],
  [(0,0,0,12,6,40),(19,0,0,12,6,40),(0,23,0,12,6,40),(19,23,0,12,6,40),(12.5,0,20,6,29,40),(90,0,35,54,110,6),(102.5,12,15,29,12,12)],
  ['Gate guide sketch: 7 mm gap for a 6 mm gate.','Cover exploded above keeper; padding/retention still pending.']),
 ('closure','F / Catch and lid-stay backing',
  [('2 catch backings',50,30,'6 / 12'),('Stay backing',50,30,'6 / 12')],
  [(0,0,0,160,6,65),(0,0,85,160,6,35),(10,6,70,50,12,30),(100,6,70,50,12,30)],
  ['Exploded backing example at the lid seam; not a drill guide.','Trace actual catches/stay; check movement and screw length.']),
]

def render(slug,title,parts,blocks,notes):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900" font-family="Arial, sans-serif">']
    def text(x,y,t,size=20,color='#253f49'):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{html.escape(str(t))}</text>')
    def rect(x,y,w,h,fill,stroke='#9c805c'):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{fill}" stroke="{stroke}"/>')
    rect(0,0,1400,900,'#f4f6f3','#f4f6f3')
    text(40,55,title,30)
    text(40,93,'MDF part set • dimensions in mm • measure before cutting',20)
    text(40,145,'PART DIAGRAM / FINISHED SIZES',21)
    text(730,145,'ISOMETRIC ASSEMBLY RENDER',21)
    # Separate rows deliberately avoid implying a kerf-free sheet nesting layout.
    for i,(label,w,h,t) in enumerate(parts):
        y=180+i*88
        if isinstance(w,int) and isinstance(h,int):
            scale=min(160/w,58/h)
            rect(50,y,w*scale,h*scale,'#d7bb91')
            if slug=='course' and i==0:
                rect(50+100*scale,y+100*scale,260*scale,260*scale,'#f4f6f3')
        else: rect(50,y,65,45,'#e6d5b8')
        text(240,y+22,label,20)
        text(240,y+49,f'{w} × {h} × {t}',19)
    # Orthographic isometric projection, fitted inside the right-hand illustration.
    def project(p):
        x,y,z=p
        return ((x-y)*.866,(x+y)*.5-z)
    polys=[]
    for x,y,z,w,d,h in sorted(blocks,key=lambda b:b[0]+b[1]+b[2]):
        a=(x,y,z+h);b=(x+w,y,z+h);c=(x+w,y+d,z+h);e=(x,y+d,z+h)
        polys.extend([( [e,c,(x+w,y+d,z),(x,y+d,z)],'#b39267'),([b,c,(x+w,y+d,z),(x+w,y,z)],'#c4a579'),([a,b,c,e],'#e4cba5')])
    pts=[project(p) for poly,_ in polys for p in poly]
    minx=min(p[0] for p in pts);maxx=max(p[0] for p in pts)
    miny=min(p[1] for p in pts);maxy=max(p[1] for p in pts)
    scale=min(570/(maxx-minx),480/(maxy-miny))
    ox=740+(570-(maxx-minx)*scale)/2;oy=190+(480-(maxy-miny)*scale)/2
    # The broad wall faces sit behind both forward-offset backing pieces.
    ordered = polys if slug == "closure" else sorted(polys, key=lambda face: sum(sum(p) for p in face[0]) / len(face[0]))
    for poly,color in ordered:
        coords=' '.join(f'{ox+(project(p)[0]-minx)*scale:.2f},{oy+(project(p)[1]-miny)*scale:.2f}' for p in poly)
        out.append(f'<polygon points="{coords}" fill="{color}" stroke="#735f47" stroke-width="1.4"/>')
    text(40,785,notes[0],21)
    text(40,825,notes[1],21)
    text(40,870,'PROVISIONAL • sketches omit hardware and wiring • verify fit before final fixing',18,'#88501f')
    out.append('</svg>')
    source=ROOT/f'build-steps-{slug}.svg';source.write_text('\n'.join(out))
    subprocess.run(['rsvg-convert','-o',str(MEDIA/f'build-steps-{slug}.png'),str(source)],check=True)

if __name__=='__main__':
    for args in SETS: render(*args)
    print('Rendered six part diagrams with matching isometric assembly views.')
