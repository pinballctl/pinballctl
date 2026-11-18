"""Reproducible, dimensioned placement drawings. No physical fit certification."""
import html
import json
import math
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
data = json.loads((P / "layout.json").read_text())
media = P
parts = []

def add(s):
    parts.append(s)

def rect(x,y,w,h,fill,stroke="#5f6f77",sw=1,extra=""):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')

def text(x,y,value,size=8,fill="#243942",anchor="start",extra=""):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" {extra}>{html.escape(value)}</text>')

def line(x,y,xx,yy,color="#6c7a80",sw=1,extra=""):
    add(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{color}" stroke-width="{sw}" {extra}/>')

def circle(x,y,r,fill,stroke="#50616a",extra=""):
    add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" {extra}/>')

def start(w,h):
    parts.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, sans-serif">')
    add('<defs><radialGradient id="ball" cx="30%" cy="25%"><stop stop-color="#fff"/><stop offset=".4" stop-color="#c8d1d6"/><stop offset="1" stop-color="#536675"/></radialGradient><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#087f85"/></marker></defs>')
    rect(0,0,w,h,"#f5f6f4","none")

def save(name):
    add('</svg>')
    (P / f'{name}.svg').write_text('\n'.join(parts))
    subprocess.run(['rsvg-convert','-o',str(media / f'{name}.png'),str(P / f'{name}.svg')],check=True)

def shell():
    rect(-10,-10,400,400,"#cfaa78","#8d6e47",1.2)
    rect(0,0,380,380,"#e4d4b8","#8d6e47")
    rect(5,5,370,370,"#efe6d5","#bea782",.5)
    for x in [80,280]:
        rect(x,-10,20,8,"#aa9a6c")

def course():
    add('<path d="M10 10H370V110H110V370H10Z" fill="#d9c6a3" stroke="#9e885e"/>')
    # Straight outer fence around a widened turning pocket; no mitred guide.
    for x,y,w,h in [(33,33,317,12),(100,75,250,12),(33,45,12,305),(75,100,12,250),(45,350,30,12),(350,45,12,30)]:
        rect(x,y,w,h,"#ae8557","#80613f",.6)
    for s in data['sensors']:
        x,y=s['xy']
        if s['axis']=='y':
            rect(x-5,13,10,20,"#314650")
            rect(x-5,87,10,20,"#314650")
            line(x,33,x,87,"#dd7962",.9,'stroke-dasharray="2 2"')
        else:
            rect(13,y-5,20,10,"#314650")
            rect(87,y-5,20,10,"#314650")
            line(33,y,87,y,"#dd7962",.9,'stroke-dasharray="2 2"')
    # Exactly three balls: one loaded, two waiting in the trough.
    for x,y in [(313.5,60),(60,309.5),(60,336.5)]:
        circle(x,y,13.5,"url(#ball)")
    circle(60,282.5,13.5,"none","#7e928c",'stroke-dasharray="2 2"')
    rect(294,45.5,6,29,"#d56841","#9d462c")
    text(313,-22,"SHOOT / READY",7.5,anchor="middle")
    text(240,-22,"ONFIELD",7.5,anchor="middle")
    text(160,-22,"BUMPER 1",7.5,anchor="middle")
    text(-19,155,"BUMPER 2",7.5,anchor="middle",extra='transform="rotate(-90 -19 155)"')
    text(-19,235,"DRAIN",7.5,anchor="middle",extra='transform="rotate(-90 -19 235)"')
    text(60,386,"3-BALL TROUGH",7.5,anchor="middle")
    for n,y in [(1,336.5),(2,309.5),(3,282.5)]:
        text(60,y+2.5,str(n),8,anchor="middle")
    for x in [275,205,125]:
        line(x,60,x-22,60,"#087f85",1.5,'marker-end="url(#arr)"')
    for y in [110,180,250]:
        line(60,y,60,y+20,"#087f85",1.5,'marker-end="url(#arr)"')

def strip(x,y,w,h,count):
    rect(x,y,w,h,"#253840","none")
    for i in range(count):
        if w>h: circle(x+(i+.5)*w/count,y+h/2,2.3,["#57c4b4","#5b92c9","#d79f66"][i%3],"none")
        else: circle(x+w/2,y+(i+.5)*h/count,2.3,["#57c4b4","#5b92c9","#d79f66"][i%3],"none")

def console():
    rect(125,125,240,240,"#dcc59e","#987b51",1.2)
    for x,y in data["console"]["fixing_screws"]:
        circle(x,y,2.1,"#bdc5c9","#151f24")
    rect(140,140,80,36,"#53735e")
    rect(145,145,70,26,"#102e69","#091c42")
    text(180,155,"PinballCTL",8,"#b6f4fd",anchor="middle")
    text(180,166,"BALL READY",7,"#b6f4fd",anchor="middle")
    strip(255,144,100,10,6)
    text(305,165,"STATUS",7.5,"#243942",anchor="middle")
    strip(255,180,100,10,6)
    text(305,201,"KEY LIGHTS",7.5,"#243942",anchor="middle")
    for b in data['buttons']:
        x,y=b['xy']
        circle(x,y,9,"#bbc2c6","#12252f")
        circle(x,y,7.5,"#e0e4e6","#677780")
        text(x,y+20,b['name'],7.2,"#243942",anchor="middle")
    for lamp in data['lamps']:
        x,y=lamp['xy']
        circle(x,y,23,"#131f26","#a4a9a8")
        circle(x,y,19,"#f6b738","#f9d58b")
        text(x,305,lamp['name'].upper(),7.3,"#243942",anchor="middle")
        text(x,y+3,"12 V",8,"#5b3f15",anchor="middle")
    # Wall strips sit higher than the course at z=110; plan view shows location.
    for r in [(90,0,200,9),(90,371,200,9),(0,90,9,200),(371,90,9,200)]:
        strip(*r,12)

def check():
    modules=data['modules']
    def overlap(a,b):
        x,y=a['xy'];w,h=a['size'];u,v=b['xy'];p,q=b['size']
        z0,z1=a['z_range'];v0,v1=b['z_range']
        return x<u+p and x+w>u and y<v+q and y+h>v and z0<v1 and z1>v0
    for i,a in enumerate(modules):
        x,y=a['xy'];w,h=a['size']
        assert 125<=x<x+w<=365 and 125<=y<y+h<=365
        for b in modules[i+1:]+data['keepouts']:
            assert not overlap(a,b),(a['name'],b['name'])
    assert 30>27 and 95+20<125
    height=data['course']['beam_height_above_floor']
    chord=2*math.sqrt(13.5**2-(height-13.5)**2)
    results={"revision":2,"nominal_3d_envelopes_nonoverlapping":True,"console_top_plus_unverified_cap_allowance":115,"conditional_closed_clearance":10,"lane_total_clearance":3,"ideal_interball_optical_window":round(27-chord,2),"beam_height":height,"pixel_count":60,"limits":data['verification_limits']}
    (P/'validation.json').write_text(json.dumps(results,indent=2)+'\n')

check()
start(1740,1150)
text(55,55,"ONE BOX / REAL BALL COURSE",32)
text(55,92,"WooDeeDoo B0973KZMGK  •  400 × 400 × 135 mm outside  •  revision 2 • Amazon audit, 18 Nov 2026",21,"#536a75")
text(55,140,"TOP / LID OPEN",22)
add('<g transform="translate(85 210) scale(2)">')
shell();course();console()
line(-10,407,390,407,"#58707c",.7)
line(-10,402,-10,412);line(390,402,390,412)
text(190,420,"400 mm",9,anchor="middle")
add('</g>')
text(960,140,"CARRIER / CONSOLE REMOVED",22)
add('<g transform="translate(975 180) scale(2.8)">')
rect(0,0,240,240,"#ece4d6","#9d8769")
for m in data['modules']:
    if m.get('layer'): continue
    x,y=m['xy'];w,h=m['size'];x-=125;y-=125
    rect(x,y,w,h,"#d4e6f1" if m.get("layer") else "#c3d4cd","#607b70",.6,'stroke-dasharray="3 2"' if m.get("layer") else "")
    words=m['name'].split(' + ')
    if m['name']=='2 lamp drivers': words=['2 lamp','drivers']
    if m.get('layer'): words=[m['name'],'UNDER PANEL']
    if m['name']=='Fuses + distribution': words=['Fuses','distribution']
    for i,word in enumerate(words): text(x+w/2,y+h/2+(i-(len(words)-1)/2)*9,word,7.1,anchor="middle")
    text(x+w/2,y+h-4,f'{w} × {h}',6.5,"#4b6259",anchor="middle")
for m in data['keepouts']:
    x,y=m['xy'];w,h=m['size'];x-=125;y-=125
    if 'wall' in m['name'] or 'cleat' in m['name']:
        rect(x,y,w,h,"#ae8557","#80613f",.7)
        continue
    rect(x,y,w,h,"#f2d5a9","#b18a4f",.7,'stroke-dasharray="3 2"')
    text(x+w/2,y+24,"LAMP TAIL",7,anchor="middle")
    text(x+w/2,y+34,"+ wire bend",6.5,anchor="middle")
add('</g>')
text(960,900,"HEIGHT / CLOSED (CONDITIONAL)",22)
add('<g transform="translate(975 1110) scale(1.5 -1.5)">')
# Inner-cavity datum only; approximate catalogue dimensions are not a box-section CAD model.
rect(0,0,380,125,"#f4eee2","#907352")
rect(5,0,370,6,"#bea17a")
rect(125,89,240,6,"#dcc59e")
rect(150,18,60,71,"#f2d5a9","#b18a4f",.7)
rect(250,6,70,44,"#c3d4cd")
rect(157,95,46,20,"#f6b738")
line(0,125,380,125,"#8d6e47",2)
add('</g>')
text(995,938,"125 mm cavity / closed lid underside",17)
text(1320,982,"95 mm panel top",17)
text(990,1080,"6 mm carrier",17)
text(55,1080,"Manual lift: trough → shooter. Lift the gate to launch; gravity returns the ball.",21)
text(55,1118,"Unresolved: lamp depth / cap, LCD thickness, ESP stack. Interface boards mount under the console.",19,"#6d6660")
save('test-bench-course-layout-v2')

start(1500,900)
text(50,55,"HOW IT FASTENS TOGETHER",30)
text(50,92,"Cross-sections • dimensions in mm • natural plywood • no printed or machined parts",21,"#536a75")
text(50,145,"CONSOLE / CARRIER SECTION",23)
# Dimensionally consistent section at 4 px per mm; z=0 lies at y=650.
# The box wall is separate from the U-frame; the drawing is a local section.
rect(60,150,40,512,"#d9ba8b")
rect(60,650,650,12,"#d9ba8b")
rect(100,626,610,24,"#c8ab7e")
rect(100,578,48,48,"#aa8558")
line(82,602,132,602,"#5a6265",4)
rect(200,294,48,332,"#b79768")
rect(248,294,48,48,"#aa8558")
rect(200,270,510,24,"#dcc59e")
line(272,268,272,330,"#5a6265",4)
# Board on 10 mm standoffs; recessed stud nuts sit flush below the 6 mm carrier.
rect(382,580,210,6,"#567b65")
for xx in [400,570]:
 rect(xx,586,12,40,"#c6cdd0")
 rect(xx-2,638,16,10,"#a8b1b5")
text(330,250,"6 mm console • top z=95",20)
text(320,325,"12 mm cleat • M3×16 top screw",19)
text(320,365,"12 mm U-frame • 83 high",19)
text(370,550,"10 mm nylon standoffs",18)
text(175,698,"6 mm carrier; recessed nuts underneath",19)
text(50,735,"Sidewall cleats retain the carrier.",19)
text(50,766,"No board screws rely on the original 3 mm bottom.",19)
text(820,145,"TROUGH SENSOR SECTION",23)
rect(840,600,565,30,"#c8ab7e")
rect(925,450,60,150,"#aa8558")
rect(1135,450,60,150,"#aa8558")
circle(1060,532.5,67.5,"url(#ball)")
# 20 mm head length in beam direction; pad height is adjustable, lens position illustrative.
rect(825,490,100,110,"#c8ab7e")
rect(1195,490,100,110,"#c8ab7e")
rect(825,460,100,40,"#314650")
rect(1195,460,100,40,"#314650")
line(925,480,1195,480,"#d76f52",2,'stroke-dasharray="7 5"')
line(1340,480,1340,600,"#6c7a80")
text(1350,548,"24 mm",19)
text(1060,675,"27 mm ball / 30 mm clear lane",20,anchor="middle")
text(820,715,"Shim pads to the actual optical axis.",19)
text(820,746,"Drill beam holes through rails; allow adjustment.",18)
text(820,777,"Three beams spaced 27 mm along the trough.",18)
text(50,840,"Gate: 6 × 29 × 40 plywood in 7 mm guides; lift 30. Trough transport cover removes for use.",20)
text(50,875,"Square corner pocket. Prove rolling and beam timing before gluing. Exact lens and fitting holes come from received parts.",18,"#6d6660")
save('test-bench-course-mounting-v2')

start(1500,1120)
text(50,55,"CONSOLE UNDERSIDE / SERVICE VIEW",30)
text(50,92,"Same x–y coordinates as the top plan • transparent view from above • NOT a mirrored drilling template",20,"#536a75")
add('<g transform="translate(65 155) scale(3.3)">')
rect(0,0,240,240,"#ece4d6","#9d8769")
for k in data['keepouts']:
 x,y=k['xy'];w,h=k['size'];x-=125;y-=125
 if 'wall' in k['name'] or 'cleat' in k['name']:
  rect(x,y,w,h,"#bc9b6f","#80613f",.5)
 else:
  rect(x,y,w,h,"#f2d5a9","#b18a4f",.6,'stroke-dasharray="3 2"')
  text(x+w/2,y+27,"LAMP TAIL",6.5,anchor="middle")
  text(x+w/2,y+37,"keep clear",6.2,anchor="middle")
# LCD reservation and button connection keepouts.
rect(15,15,90,50,"#d2ddeb","#657b97",.6,'stroke-dasharray="3 2"')
text(60,36,"LCD RESERVATION",6.5,anchor="middle")
text(60,48,"90 × 50 • depth unverified",5.5,anchor="middle")
for b in data['buttons']:
 x,y=b['xy'];x-=125;y-=125
 circle(x,y,12,"#e8e9e5","#889492",'stroke-dasharray="2 1"')
 circle(x,y,8,"#bfc6c7")
 text(x,y+3,b['name'],4.8,anchor="middle")
for m in data['modules']:
 if not m.get('layer'):continue
 x,y=m['xy'];w,h=m['size'];x-=125;y-=125
 rect(x,y,w,h,"#bad1d5","#537a81",.6)
 if m['name']=='Interface board':
  text(x+w/2,y+15,"INTERFACE",7,anchor="middle")
  text(x+w/2,y+27,"70 × 50 PCB",6.2,anchor="middle")
  text(x+w/2,y+39,"components downward",5.6,anchor="middle")
 else:
  for i in range(3):
   rect(x+2+i*33,y+.7,29.9,18.6,"#d9d9cf","#7f8987",.3)
   for j in range(5):rect(x+4+i*33+j*5.2,y+3,3.5,6,"#df953c","none")
for x,y in data['console']['fixing_screws']:
 circle(x-125,y-125,2,"#263c45","none")
add('</g>')
for yy,title,lines in [
 (165,"THREE DISTINCT HEIGHTS",["Carrier boards: z=6–51","Interface: z=60–89","Power connectors: z=65–89"]),
 (330,"REMOVABLE PANEL",["Four screws land on plywood cleats.","Their coordinates avoid controls:","(245,143)  (347,207)","(143,325)  (347,330)"]),
 (530,"SERVICE HARNESS",["Allow 150–200 mm relaxed loops.","Retain WAGOs with saddles/ties.","Keep levers and Pi fan accessible.","Route bundles around button tails."]),
 (730,"CONDITIONAL FIT",["LCD and lamp thicknesses unknown.","ESP stack must remain below z=50.","No physical assembly has been tested."])
]:
 text(930,yy,title,21)
 for j,t in enumerate(lines):text(930,yy+38+j*30,t,18)
text(60,1015,"Grey circles include a nominal 24 mm wiring zone around each Ø16 switch; reserve to z=60.",20)
text(60,1050,"Connector bodies fit the two rows; their leads exit into the adjacent gaps and turn downward.",20)
text(60,1085,"Natural plywood supports and top are removable by hand tools. All placement dimensions are design allowances.",19,"#6d6660")
save('test-bench-course-underside-v2')
print('Rendered three drawings and checked proposed placement envelopes.')
