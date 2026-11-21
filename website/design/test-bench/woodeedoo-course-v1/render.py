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
    # Continuous outer and inner L-shaped fences with square butt joints.
    for x,y,w,h in [(33,33,317,12),(75,75,275,12),(33,45,12,305),(75,87,12,263),(45,350,30,12),(350,45,12,30)]:
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
    rect(152,143,76,30,"#243942")
    rect(155,145,70,26,"#102e69","#091c42")
    text(190,155,"PinballCTL",8,"#b6f4fd",anchor="middle")
    text(190,166,"BALL READY",7,"#b6f4fd",anchor="middle")
    strip(255,144,100,10,6)
    text(305,165,"STATUS",7.5,"#243942",anchor="middle")
    strip(255,180,100,10,6)
    text(305,201,"KEY LIGHTS",7.5,"#243942",anchor="middle")
    for b in data['buttons']:
        x,y=b['xy']
        circle(x,y,data["button_spec"]["face_diameter"]/2,"#bbc2c6","#12252f")
        circle(x,y,4.7,"#4ba7ff","#167ac9")
        circle(x,y,3.7,"#e0e4e6","#677780")
        text(x,y+20,"INPUT" if b.get('flipper') else b['name'],7.2,"#243942",anchor="middle")
    for lamp in data['lamps']:
        x,y=lamp['xy']
        circle(x,y,lamp['bezel_diameter']/2,"#bbc2c6","#50616a")
        circle(x,y,data['lamp_spec']['luminous_diameter']/2,"#f6b738","#f9d58b")
        text(x,y+20,"OUTPUT",7.2,"#243942",anchor="middle")
        text(x,y+2,"12 V",5.5,"#5b3f15",anchor="middle")
        button=next(b for b in data['buttons'] if b.get('flipper')==lamp['flipper'])
        text((x+button['xy'][0])/2,310,lamp['flipper'].upper()+" FLIPPER",7.3,anchor="middle")
    # One continuous strip with a small feed gap and gentle corner bends.
    # Its plan centreline lies about 1 mm in from the nominal inner wall.
    add('<rect x="1" y="1" width="378" height="378" rx="10" fill="none" stroke="#253840" stroke-width="3"/>')
    straight=358
    arc=math.pi*10/2
    perimeter=4*(straight+arc)
    def rim_point(distance):
        t=distance%perimeter
        for side in range(4):
            if t<=straight:
                return [(11+t,1),(379,11+t),(369-t,379),(1,369-t)][side]
            t-=straight
            if t<=arc:
                angle=math.radians(-90+90*side)+t/10
                cx,cy=[(369,11),(369,369),(11,369),(11,11)][side]
                return cx+10*math.cos(angle),cy+10*math.sin(angle)
            t-=arc
        return 11,1
    for i in range(89):
        x,y=rim_point(straight+arc+(290.75-11)+(i+.5)*1000/60)
        circle(x,y,2.3,["#57c4b4","#5b92c9","#d79f66"][i%3],"none")
    rect(376.5,279.25,5,11.5,"#e4d4b8","none")
    # Right-side feed / return wiring drops to the existing console-side passage.
    for yy,col in [(282,"#b54840"),(285,"#243942"),(288,"#b99731")]:
        line(379,yy,371,yy,col,.9)
        line(371,yy,371,295+(yy-282)/3,col,.9)
    line(371,300,371,311,"#087f85",1,'marker-end="url(#arr)"')
    text(387,286,"LED FEED",5.8,"#243942",extra='transform="rotate(90 387 286)"')
    text(396,286,"DOWN TO BAY",5.8,"#243942",extra='transform="rotate(90 396 286)"')

def check():
    lcd=data['console']['lcd']
    modules=data['modules']+[{
        'name':'LCD rear assembly and retaining tabs',
        'xy':lcd['xy'], 'size':lcd['reservation'][:2],
        'z_range':lcd['z_range'],
    }]
    # Include the wiring space behind every button, not just the larger modules.
    radius=data['button_spec']['wire_zone_diameter']/2
    panel_top=data['console']['top_z']
    modules += [{
        'name':b['name']+' button wires',
        'xy':[b['xy'][0]-radius,b['xy'][1]-radius],
        'size':[2*radius,2*radius],
        'z_range':[panel_top-data['button_spec']['rear_allowance'],panel_top],
    } for b in data['buttons']]
    def overlap(a,b):
        x,y=a['xy'];w,h=a['size'];u,v=b['xy'];p,q=b['size']
        z0,z1=a['z_range'];v0,v1=b['z_range']
        return x<u+p and x+w>u and y<v+q and y+h>v and z0<v1 and z1>v0
    for i,a in enumerate(modules):
        x,y=a['xy'];w,h=a['size']
        max_x=380 if a.get('boundary')=='box' else 365
        assert 125<=x<x+w<=max_x and 125<=y<y+h<=365
        for b in modules[i+1:]+data['keepouts']:
            assert not overlap(a,b),(a['name'],b['name'])
    lamp_top=panel_top+data['lamp_spec']['top_allowance']
    control_top=max(lamp_top,panel_top+data['button_spec']['top_allowance'],lcd['z_range'][1])
    cavity_height=data['box']['inside_approx'][2]
    assert 30>27 and control_top<cavity_height
    height=data['course']['beam_height_above_floor']
    chord=2*math.sqrt(13.5**2-(height-13.5)**2)
    results={"revision":data['revision'],"nominal_3d_envelopes_nonoverlapping":True,"button_wire_zones_checked":len(data['buttons']),"console_top_plus_unverified_cap_allowance":control_top,"conditional_lamp_lid_clearance":cavity_height-lamp_top,"conditional_closed_clearance":cavity_height-control_top,"lane_total_clearance":3,"ideal_interball_optical_window":round(27-chord,2),"beam_height":height,"pixel_count":data["lighting"]["total_pixels"],"maximum_design_pixels":102,"conditional_lcd_top":100,"conditional_lcd_lid_clearance":25,"limits":data['verification_limits']}
    (P/'validation.json').write_text(json.dumps(results,indent=2)+'\n')

check()
start(1740,1150)
text(55,55,"ONE BOX / REAL BALL COURSE",32)
text(55,92,f"WooDeeDoo B0973KZMGK  •  400 × 400 × 135 mm outside  •  revision {data['revision']} • separate flipper inputs / outputs • 21 Nov 2026",21,"#536a75")
text(55,119,"PROVISIONAL: power stack, fuse holders and inlet have reserved space; actual depths, wiring and MDF fixings need checking.",18,"#945015")
text(55,150,"TOP / LID OPEN",22)
add('<g transform="translate(85 210) scale(2)">')
shell();course();console()
line(-10,407,390,407,"#58707c",.7)
line(-10,402,-10,412);line(390,402,390,412)
text(190,420,"400 mm",9,anchor="middle")
add('</g>')
text(960,150,"CARRIER / CONSOLE REMOVED",22)
add('<g transform="translate(975 180) scale(2.8)">')
rect(0,0,240,240,"#ece4d6","#9d8769")
for m in data['modules']:
    if m.get('layer'): continue
    x,y=m['xy'];w,h=m['size'];x-=125;y-=125
    rect(x,y,w,h,"#d4e6f1" if m.get("layer") else "#c3d4cd","#607b70",.6,'stroke-dasharray="3 2"' if m.get("layer") else "")
    words=m['name'].split(' + ')
    if m['name']=='2 MOSFET drivers': words=['2 MOSFET','drivers']
    if m['name']=='Main 12V fuse': words=['MAIN 12 V','P18 × 1']
    if m['name']=='Two 5V fuses': words=['5 V FUSES','P18 × 2']
    if m['name']=='XT60 + leads': words=['XT60','candidate']
    if m.get('layer'): words=[m['name'],'UNDER PANEL']
    if m['name']=='Fuses + distribution': words=['Fuses','distribution']
    for i,word in enumerate(words): text(x+w/2,y+h/2+(i-(len(words)-1)/2)*9,word,7.1,anchor="middle")
    text(x+w/2,y+h-4,f'{w} × {h}',6.5,"#4b6259",anchor="middle")
for m in data['keepouts']:
    x,y=m['xy'];w,h=m['size'];x-=125;y-=125
    if 'wall' in m['name'] or 'cleat' in m['name']:
        if 'passage' in m['name']: continue
        rect(x,y,w,h,"#ae8557","#80613f",.7)
        continue
    rect(x,y,w,h,"none","#b18a4f",.7,'stroke-dasharray="3 2"')
rect(228,135,12,50,"none","#a56c33",.7,'stroke-dasharray="2 2"')
text(249,132,"SIDE PASSAGE",5.5,anchor="middle")
text(249,190,"50 × 45 high",5.5,anchor="middle")
add('</g>')
text(975,876,"Dashed amber outlines: lamp bodies / wires above the carrier bays.",16,"#7f5b32")
text(960,900,"HEIGHT / CLOSED (CONDITIONAL)",22)
add('<g transform="translate(975 1110) scale(1.5 -1.5)">')
# Inner-cavity datum only; approximate catalogue dimensions are not a box-section CAD model.
rect(0,0,380,125,"#f4eee2","#907352")
rect(5,0,370,6,"#bea17a")
rect(125,89,240,6,"#dcc59e")
rect(187,60,36,29,"#f2d5a9","#b18a4f",.7)
rect(250,6,70,44,"#c3d4cd")
rect(192.6,95,24.8,5,"#f6b738")
rect(163,95,14,10,"#6bb4d8")
rect(270,65,80,24,"#c3d4cd")
rect(277,89,66,11,"#102e69")
line(0,125,380,125,"#8d6e47",2)
add('</g>')
text(975,918,"Pi + GeeekPi: z≤58 allowance • LCD rear z≥65 • nominal gap 7 mm",14)
text(1558,976,"Panel top",16)
text(1558,998,"z=95 mm",16)
text(990,1080,"6 mm carrier",17)
text(55,1080,"Manual lift: trough → shooter. Lift the gate to launch; gravity returns the ball.",21)
text(55,1118,"10 × 12mm Momentary Blue LED High Head buttons • Ø14 faces • 89 + 6 + 6 pixels • fit remains conditional.",19,"#6d6660")
save(f"test-bench-course-layout-v{data['revision']}")

start(1500,900)
text(50,55,"MOUNTING GEOMETRY / MDF FIXINGS PENDING",30)
text(50,92,"Cross-sections • dimensions in mm • 6 / 12 mm MDF sheets • no printed or machined parts",21,"#536a75")
text(50,118,"REFERENCE ENVELOPES ONLY: measure the assembled power stack and specify fixing pads before drilling.",18,"#945015")
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
# Reserve the complete bay without assuming a verified Pi / power-board stack.
rect(370,418,270,208,"#dce7e1","#567b65",1.5,extra='stroke-dasharray="6 4"')
text(505,476,"Assembly layout pending",17,anchor="middle")
text(505,510,"Cooler / cables / controls",17,anchor="middle")
text(330,250,"6 mm console • top z=95",20)
text(320,325,"Fixing pad: size / attachment pending",19)
text(320,365,"12 mm U-frame • 83 high",19)
text(370,410,"Pi + cooler + GeeekPi bay",18)
text(320,550,"Reserved space; fit unverified",16)
text(320,575,"Whole assembly must fit z=6–58",16)
text(175,698,"6 mm MDF carrier; no recessed nuts",19)
text(50,735,"Sidewall cleats retain the carrier.",19)
text(50,766,"Board retention pending; keep the original bottom unloaded by screw tips.",18)
text(820,145,"TROUGH SENSOR SECTION",23)
rect(840,600,565,30,"#c8ab7e")
rect(925,450,60,150,"#aa8558")
rect(1135,450,60,150,"#aa8558")
circle(1060,532.5,67.5,"url(#ball)")
# 5 px/mm: use the selected head height; centred optical axis is illustrative only.
head_height = data["sensor_spec"]["head_dimensions_mm"][2] * 5
head_top, head_bottom = 480 - head_height / 2, 480 + head_height / 2
for x in (825, 1195):
    rect(x,head_bottom,100,600-head_bottom,"#c8ab7e")
    rect(x,head_top,100,head_height,"#314650")
line(925,480,1195,480,"#d76f52",2,'stroke-dasharray="7 5"')
line(1340,480,1340,600,"#6c7a80")
text(1350,548,"24 mm",19)
text(1060,675,"27 mm ball / 30 mm clear lane",20,anchor="middle")
text(820,715,"Shim pads to the actual optical axis.",19)
text(820,746,"5 mm optics: prove rail apertures with one pair.",18)
text(820,777,"Three beams spaced 27 mm along the trough.",18)
text(50,840,"Gate: 6 × 29 × 40 MDF in 7 mm guides; lift 30. Transport-cover fixings are not yet specified.",20)
text(50,875,"Continuous L fence. Prove the 30 mm turn and beam timing before gluing. Exact lens and fitting holes come from received parts.",18,"#6d6660")
save(f"test-bench-course-mounting-v{data['revision']}")

start(1500,1120)
text(50,55,"CONSOLE UNDERSIDE / SERVICE VIEW",30)
text(50,92,"Same x–y coordinates as the top plan • transparent view from above • NOT a mirrored drilling template",20,"#536a75")
text(50,125,"PROVISIONAL: carrier power stack and holder reservations are shown in the layout; final fixings and routing require measurement.",17,"#945015")
add('<g transform="translate(65 155) scale(3.3)">')
rect(0,0,240,240,"#ece4d6","#9d8769")
for k in data['keepouts']:
 x,y=k['xy'];w,h=k['size'];x-=125;y-=125
 if 'wall' in k['name'] or 'cleat' in k['name']:
  if 'passage' in k['name']: continue
  rect(x,y,w,h,"#bc9b6f","#80613f",.5)
 else:
  rect(x,y,w,h,"#f2d5a9","#b18a4f",.6,'stroke-dasharray="3 2"')
  text(x+w/2,y+14,"LAMP TAIL",5.8,anchor="middle")
  text(x+w/2,y+24,"z=60–95",5.5,anchor="middle")
# LCD reservation and button connection keepouts.
rect(15,15,100,50,"#d2ddeb","#657b97",.6,'stroke-dasharray="3 2"')
text(65,36,"LCD BACK / RETAINERS",6.5,anchor="middle")
text(65,48,"100 × 50 • below panel",5.5,anchor="middle")
for b in data['buttons']:
 x,y=b['xy'];x-=125;y-=125
 circle(x,y,12,"#e8e9e5","#889492",'stroke-dasharray="2 1"')
 circle(x,y,data["button_spec"]["hole_diameter"]/2,"#6bb4d8")
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
 (165,"THREE DISTINCT HEIGHTS",["Carrier / power stack: z=6–58","Interface: z=60–89","Power connectors: z=65–89"]),
 (330,"REMOVABLE PANEL",["MDF pad sizes / fixings pending.","Fixing centres: reference only.","(249,143)  (347,207)","(143,325)  (347,330)"]),
 (530,"SERVICE HARNESS",["Normal bundles: 150–200 mm loops.","LED data: short; unplug before lifting.","Retain WAGOs with saddles/ties.","Keep levers and Pi fan accessible.","Route bundles around button tails."]),
 (730,"CONDITIONAL FIT",["LCD rear z≥65; Pi stack z≤58.","7 mm nominal gap; measure / load-test.","ESP stack must remain below z=50.","No physical assembly has been tested."])
]:
 text(930,yy,title,21)
 for j,t in enumerate(lines):text(930,yy+38+j*30,t,18)
text(60,1015,"10 × 12mm Momentary Blue LED High Head buttons; grey Ø24 wire zones. Rear depth to z=60 is conditional.",20)
text(60,1050,"Each flipper pair: one blue input button + one yellow MOSFET-switched lamp. Lamp wired rear allowance: 35 mm.",20)
text(60,1085,"6 / 12 mm MDF. Small pad envelopes are placement references; final fixings require a clearance check.",19,"#6d6660")
save(f"test-bench-course-underside-v{data['revision']}")
print('Rendered three drawings and checked proposed placement envelopes.')
