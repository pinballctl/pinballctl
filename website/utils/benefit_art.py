"""Context-specific vector scenes in the homepage's circuit/playfield style.

Only drawing primitives are shared. Every panel has an explicit composition;
never substitute a generic illustration when a new panel is added.
"""
from html import escape
from functools import cache

MINT = '#67e8c3'
PEACH = '#ffae71'


def box(x, y, w, h, color='#142b38', radius=9):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{color}" stroke="#4e8b91" stroke-width="2"/>'


def line(d, color=MINT, width=3, dashed=False):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'+(' stroke-dasharray="4 7"' if dashed else '')+'/>'


def dot(x, y, r=7, color=PEACH):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'


def text(x, y, value, size=12, color='#abc0cf'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{escape(value)}</text>'


def chip(x, y, name, w=78, h=70):
    pins = ''.join(line(f'M{x-9} {y+15+i*16}h9m{w} 0h9',PEACH,4) for i in range(3))
    return pins+box(x,y,w,h,'#244653')+text(x+10,y+h/2+4,name)


def screen(x,y,w=140,h=100):
    return box(x,y,w,h,'#355568')+box(x+7,y+7,w-14,h-14)+line(f'M{x+w/2} {y+h}v10m-24 0h48','#4e8b91',4)


def arrow(x,y,length=45):
    return line(f'M{x} {y}h{length}m-8-6 8 6-8 6')


def check(x,y):
    return line(f'm{x} {y} 9 9 17-22',MINT,4)


def speaker(x,y):
    return f'<path d="M{x} {y+16}h14l19-16v60l-19-16h-14Z" fill="#355568" stroke="{MINT}" stroke-width="2"/>'+line(f'M{x+45} {y+12}q20 18 0 36','#4e8b91',4)


def coil(x,y):
    return line(f'M{x} {y+42}h12m55 0h18','#4e8b91',4)+''.join(f'<ellipse cx="{x+17+i*10}" cy="{y+25}" rx="9" ry="28" fill="#142b38" stroke="{PEACH}" stroke-width="3"/>' for i in range(5))


def playfield(x,y):
    return box(x,y,94,132,'#355568',16)+box(x+7,y+7,80,118)+dot(x+30,y+39,12,MINT)+dot(x+64,y+61,12,MINT)+dot(x+34,y+83,12,MINT)+line(f'M{x+18} {y+108}l24 9m34-9-24 9',PEACH,7)


def document(x,y,heading):
    return box(x,y,90,112)+text(x+10,y+24,heading,11)+line(f'M{x+12} {y+44}h60m-60 19h45m-45 19h55','#4e8b91',4)


def badge(x,y,name):
    return box(x,y,90,30)+text(x+9,y+20,name,11)


def browser(x,y,w=200,h=125):
    return screen(x,y,w,h)+line(f'M{x+8} {y+24}h{w-16}','#4e8b91',2)+dot(x+17,y+16,3)+dot(x+29,y+16,3,MINT)


@cache
def drawings():
    """Each entry matches one specific benefit, overview or onboarding panel."""
    return {
      'hardware': [
        (chip(35,45,'GPIO')+line('M113 65h50v-25h30m-30 25v55h30')+badge(194,25,'FLIPPER')+badge(194,105,'BUMPER'),'PIN MAP'),
        (coil(36,57)+arrow(125,85,38)+chip(183,47,'ESP')+line('M184 121h76',PEACH,4)+text(194,143,'MAX ON',10),'LIMITS ENFORCED LOCALLY'),
        (coil(30,55)+coil(160,55)+line('M252 78h49v-35m0 35v45')+dot(301,43)+dot(301,123,7,MINT)+text(28,137,'PULSE',10)+text(164,137,'PAIRED',10),'DRIVERS FOR DIFFERENT COILS')],
      'hardware-mapping': [
        (badge(20,30,'GPIO 6')+badge(20,105,'GPIO 7')+line('M110 45h43v38h35m-78 37h43V83')+box(189,53,139,61)+text(201,80,'LEFT FLIPPER',12)+text(201,99,'named component',9),'FROM PIN TO PURPOSE'),
        (box(34,24,285,115)+text(49,49,'PIN',10)+text(108,49,'FUNCTION',10)+text(214,49,'DRIVER',10)+line('M48 61h255','#4e8b91',2)+text(49,94,'6',18)+box(101,73,91,33)+text(113,94,'COIL')+box(211,73,92,33)+text(221,94,'PULSE')+line('m179 86-4 5-4-5'),'ONE ROW, ALL THE OPTIONS')],
      'rules-scoring': [
        (dot(42,80,16)+arrow(65,80,40)+box(123,43,92,76)+text(139,85,'IF HIT')+arrow(228,80,35)+speaker(280,50),'INPUT BECOMES A RESPONSE'),
        (dot(52,80,22,MINT)+dot(52,80,11)+arrow(83,80)+screen(149,37,160,89)+text(175,91,'+100',32,MINT),'TURN HITS INTO REWARDS'),
        (box(35,27,194,112)+chip(53,46,'ESP')+line('M132 80h23')+coil(157,60)+text(251,67,'PI',17)+line('M231 83h70','#4e8b91',2,True),'FAST OUTPUTS STAY ON THE ESP')],
      'lighting': [
        (playfield(127,12)+line('M45 43h90m86 64h74','#4e8b91',2,True)+box(25,29,26,26)+dot(38,42,6,MINT)+box(289,94,26,26)+dot(302,107,6,PEACH),'LIGHTS IN PLAYFIELD CONTEXT'),
        (dot(54,78,21,PEACH)+line('M54 38v-10m-32 50H12m42 40v10')+arrow(88,78,42)+box(151,34,171,101)+''.join(dot(174+i*37,62+j*43,9,MINT if (i+j)%2 else PEACH) for i in range(4) for j in range(2)),'ONE FLASH OR A WHOLE SCENE'),
        (screen(26,37,132,90)+dot(59,66,9,MINT)+dot(109,96,9)+arrow(168,80,42)+chip(231,49,'ESP')+text(50,146,'PREVIEW',10),'PREVIEW BEFORE DEPLOYMENT')],
      'audio-media': [
        (dot(42,80,15)+arrow(63,80,35)+box(113,38,98,85)+line('M128 83v-12m15 29V55m15 48V62m15 29V70m15 18v-9',MINT,5)+arrow(222,80,24)+speaker(260,50),'EVENT-DRIVEN AUDIO'),
        (box(26,25,85,61,'#244653')+box(45,53,85,61)+arrow(144,80,30)+screen(195,29,135,111)+dot(263,81,21,PEACH),'COMPOSE A BACKGLASS'),
        (browser(22,30,130,100)+text(46,93,'GODOT',18,MINT)+arrow(164,82,30)+screen(220,22,98,123)+text(238,62,'GAME',14)+dot(270,99,16),'FROM EDITOR TO MACHINE')],
      'live-view': [
        (browser(39,15,276,130)+line('M66 111l28-18 32 21 37-40 26 15')+dot(246,61,15,MINT)+dot(263,107,12)+line('M78 62h47',PEACH,7),'A PLAYFIELD YOU CAN EXERCISE'),
        (box(17,54,70,57)+text(29,87,'KEY')+arrow(95,83,25)+chip(137,48,'ESP',64)+arrow(214,83,26)+chip(257,48,'PI',62),'SIMULATED INPUT, SHARED ROUTE'),
        (screen(26,37,118,93)+dot(84,81,16,MINT)+line('M177 31v103','#4e8b91',2,True)+coil(219,57)+text(43,150,'PREVIEW',10)+text(218,150,'REAL OUTPUT',10),'VALIDATE BOTH SCREEN AND MACHINE')],
      'diagnostics': [
        (box(35,25,289,118)+line('M56 52h246m-246 28h246m-246 28h246','#284553',2)+line('M57 115l39-21 29 5 33-45 36 29 42-15 65-24')+dot(158,54,6),'FOLLOW EVENT THROUGHPUT'),
        (document(32,22,'EVENTS')+line('M139 52h64l-24 28v28l-17 10V80Z',PEACH,3)+arrow(211,81,26)+badge(253,66,'MATCH'),'SEPARATE SIGNAL FROM NOISE'),
        (box(20,47,81,70)+line('M48 67v29m25-29v29',PEACH,6)+arrow(113,83,29)+box(156,47,67,70)+check(176,84)+arrow(235,83,28)+dot(303,82,24,MINT)+line('m295 71 17 11-17 11Z','#142b38',3),'PAUSE, CHECK HEALTH, RECOVER')],
      'esp-connection': [
        (chip(34,47,'PI',82)+line('M126 81h91',MINT,3,True)+chip(233,37,'ESP32',83,90)+dot(300,50,5,MINT),'IDENTITY + CONNECTION STATUS'),
        (browser(28,24,150,115)+box(46,66,110,26)+dot(62,79,6,MINT)+text(77,83,'BRIDGE',10)+line('M179 81h49')+chip(245,47,'ESP',70),'BRIDGE CONTROLS IN ONE PLACE')],
      'firmware': [
        (document(45,22,'RELEASES')+badge(160,24,'v1.2')+badge(178,66,'v1.3')+badge(196,108,'v1.4')+check(302,122),'CHOOSE THE RIGHT RELEASE'),
        (box(28,33,98,96)+line('M77 49v45m-17-17 17 17 17-17',MINT,4)+arrow(140,81,38)+chip(199,46,'FLASH',90)+check(305,118),'DOWNLOAD, FLASH, VERIFY')],
      'accelerometer': [
        (box(94,45,171,60,'#244653')+line('M37 116h286','#4e8b91',3)+dot(180,75,13,MINT)+line('M180 33V16m0 100v24',PEACH,3)+text(132,155,'BASELINE',10),'ESTABLISH THE RESTING POSITION'),
        (line('M44 130V28m0 102h276','#4e8b91',2)+line('M48 76l25-13 20 38 26-57 25 32 29-14 27 32 28-44 30 22 54-6')+line('M48 107l44-9 36 15 39-13 30 8 34-11 46 12 35-7',PEACH,2)+text(269,35,'X Y Z',12),'SEE CHANGES ON THREE AXES')],
      'supported-components': [
        (chip(128,45,'ESP',82)+line('M128 80H87V35H58m29 45v48H58m122-48h42')+dot(42,35,12,MINT)+coil(11,105)+speaker(262,51),'A CONNECTED HARDWARE ECOSYSTEM'),
        (box(63,22,233,121)+text(79,47,'COMPONENT',11)+text(220,47,'SUPPORT',10)+line('M79 58h199','#4e8b91',2)+text(79,85,'BOARD')+check(234,81)+text(79,121,'DRIVER')+dot(248,116,7,PEACH),'CHECK EACH COMPONENT AND DRIVER')],
      'rule-editor': [
        (badge(13,63,'TRIGGER')+arrow(106,78,20)+f'<path d="m184 35 43 43-43 43-43-43Z" fill="#244653" stroke="{MINT}" stroke-width="2"/>'+text(171,82,'IF')+arrow(230,78,20)+badge(257,63,'ACTION'),'BUILD CONDITIONAL RESPONSES'),
        (box(43,24,274,119)+text(61,51,'LEFT TARGET HIT',13,MINT)+line('M62 62v51h29','#4e8b91',2)+badge(99,73,'ADD SCORE')+badge(207,102,'PLAY CUE'),'READ YOUR RULES LIKE A PLAN')],
      'scoring': [
        (box(32,43,71,85)+dot(67,71,16,MINT)+dot(67,71,7)+arrow(113,83,35)+box(166,42,151,87)+text(182,74,'TARGET HIT',11)+text(188,110,'+250',29,MINT),'POINTS FOR THE RIGHT TARGET'),
        (dot(47,64,17,MINT)+dot(117,64,17,MINT)+dot(187,64,17,PEACH)+line('M47 96v26h140V96')+arrow(214,83,25)+text(255,95,'×3',36,MINT),'LINK HITS INTO A COMBINATION')],
      'playfield-layout': [
        (playfield(139,12)+box(31,30,61,94)+dot(61,55,10,MINT)+dot(61,94,10,PEACH)+line('M91 55h30l18-10',MINT,2,True)+line('M251 101h55m-25-25v50','#4e8b91',2),'PLACE COMPONENTS ON YOUR LAYOUT'),
        (playfield(47,12)+arrow(155,79,34)+box(213,37,102,93)+text(232,65,'LIVE')+line('m241 78 31 14-15 5-4 17Z',PEACH,3),'USE THE LAYOUT TO TEST EVENTS')],
      'audio': [
        (document(38,24,'SOUNDS')+line('M55 81v-8m13 20V65m13 33V69m13 18v-8',MINT,4)+line('M130 79h36v-37h38m-38 37v44h38')+badge(212,26,'HIT CUE')+badge(212,108,'MODE CUE'),'ORGANISE ASSETS INTO CUES'),
        (speaker(34,52)+box(124,29,197,107)+line('M146 57h150m-150 25h150m-150 25h150','#4e8b91',3)+dot(190,57,8,MINT)+dot(264,82,8,PEACH)+dot(222,107,8,MINT),'SHAPE HOW PLAYBACK BEHAVES')],
      'media': [
        (box(48,21,180,87,'#355568')+box(82,47,180,87,'#244653')+box(116,73,180,76)+text(132,99,'SCORE',15)+dot(268,116,16,PEACH),'BUILD A SCENE FROM LAYERS'),
        (screen(28,31,136,88)+screen(207,24,111,119)+line('M164 76h21v14h22',MINT,3,True)+text(48,83,'BACKGLASS',10)+text(225,78,'DISPLAY',10)+text(250,101,'2',20,MINT),'ASSIGN SCENES TO YOUR DISPLAYS')],
      'godot': [
        (browser(26,17,307,132)+line('M110 43v94M42 109h272','#4e8b91',2)+text(41,61,'SCENE',10)+line('M46 74h44m-44 14h30',MINT,3)+box(174,57,66,39,'#244653')+dot(207,77,10,PEACH),'AUTHOR IN THE GODOT EDITOR'),
        (badge(17,64,'GAME EVENT')+arrow(115,79,33)+screen(164,24,165,122)+text(188,61,'SCENE',12)+dot(246,99,23,PEACH)+line('M211 99h-15m85 0h15M246 64V51',MINT,3),'LET GAME EVENTS CHANGE THE SCENE')],
      'dashboard': [
        (box(35,23,288,120)+box(50,39,76,87)+dot(88,66,15,MINT)+text(65,108,'READY',10)+box(138,39,78,38)+line('M151 63l14-12 14 8 22-10')+box(230,39,78,38)+text(246,64,'ESP',13)+box(138,89,170,37)+dot(153,107,5,MINT)+text(168,112,'CONNECTED',11),'THE MACHINE AT A GLANCE'),
        (box(39,29,102,102)+box(53,44,73,25)+box(53,80,73,33)+line('M141 58h48v28h24',MINT,2,True)+document(219,25,'DETAIL')+dot(113,57,5,PEACH),'OPEN THE DETAIL BEHIND THE STATUS')],
      'event-logs': [
        (badge(17,20,'ESP')+badge(17,68,'BRIDGE')+badge(17,116,'HOST')+line('M107 35h37v97m-37-49h37m-37 48h37m0-48h42')+document(201,25,'EVENTS'),'CHOOSE WHICH SOURCE TO FOLLOW'),
        (document(42,21,'LOG')+f'<circle cx="233" cy="70" r="34" fill="#193740" stroke="{MINT}" stroke-width="4"/>'+line('M258 96l35 38',PEACH,7)+text(207,75,'MATCH',11)+line('M135 77h54','#4e8b91',2,True),'FIND THE EVENT THAT MATTERS')],
      'service-log': [
        (document(172,23,'SERVICE')+line('M55 39l51 51m-58 34 59-61',PEACH,9)+dot(56,40,12,'#355568')+arrow(118,81,32),'TURN MAINTENANCE INTO A RECORD'),
        (line('M61 28v110','#4e8b91',3)+dot(61,38,7,MINT)+dot(61,83,7,PEACH)+dot(61,128,7,MINT)+badge(89,23,'INSPECT')+badge(122,68,'REPAIR')+badge(155,113,'RETEST'),'LOOK BACK THROUGH THE SERVICE HISTORY')],
      'integrity-check': [
        (badge(18,22,'ASSET')+badge(18,108,'INPUT')+line('M108 37h42v85m-42 0h42m0-43h27')+badge(182,64,'RULE')+line('M272 79h20v-40h25m-25 40v46h25')+dot(323,39,9,MINT)+dot(323,125,9,PEACH),'TRACE REFERENCES ACROSS THE PROJECT'),
        (document(52,21,'REVIEW')+box(181,35,117,97)+text(196,59,'REFERENCE',10)+line('M197 77h37m20 0h25',PEACH,4)+text(204,115,'CHECK',12)+line('M145 80h24','#4e8b91',2,True),'REVIEW BROKEN REFERENCES BEFORE EDITING')],
      'settings': [
        (browser(35,20,289,126)+text(53,60,'PROJECT',12)+line('M55 78h94m-94 30h94','#4e8b91',3)+box(178,46,126,32)+text(189,67,'MY MACHINE',11)+box(178,94,126,30)+dot(280,109,8,MINT),'CONFIGURE YOUR PROJECT'),
        (document(29,26,'PROJECT')+arrow(132,58,37)+box(181,40,62,70,'#355568')+text(190,80,'FILE',12)+line('M167 115h-35m8-6-8 6 8 6')+arrow(255,79,30)+text(290,84,'PI',18,MINT),'EXPORT AND RESTORE YOUR WORK')],
      'wifi': [
        (chip(35,51,'PI',72)+line('M134 58q45-47 90 0m-72 22q27-29 54 0m-36 21q9-10 18 0',MINT,5)+dot(179,119,5,PEACH)+box(255,68,68,57)+line('M270 68V35m38 33V35','#4e8b91',4)+dot(273,108,4,MINT),'CHECK THE HOST NETWORK LINK'),
        (browser(31,24,204,119)+text(48,63,'NETWORK',12)+box(48,76,168,26)+text(57,94,'HOME WI-FI',10)+arrow(246,85,24)+chip(285,59,'PI',48,54),'MANAGE HOST WI-FI IN YOUR BROWSER')],
      'performance': [
        (box(16,51,74,66)+text(26,88,'SEND',12)+arrow(97,70,53)+chip(166,46,'ESP',62)+line('M227 132H53V119',PEACH,3)+text(102,151,'CONFIRM',10)+arrow(241,79,24)+check(285,83),'FOLLOW DELIVERY AND ITS CONFIRMATION'),
        (box(27,24,307,119)+line('M46 112V44m0 68h268','#4e8b91',2)+''.join(box(64+i*34,109-h,18,h,'#244653',3) for i,h in enumerate([17,27,41,65,47,25]))+line('M59 90l36-11 34 8 34-39 35 16 35 17 36-12 36 15',PEACH,3),'COMPARE RATE, BACKLOG AND LATENCY'),
        (coil(30,55)+line('M120 84h40m38 0h42','#4e8b91',3)+line('M160 84l34-29',PEACH,5)+chip(256,48,'ESP',68)+text(138,127,'DISARMED',12,PEACH),'STOP ACTIVATIONS WHEN DELIVERY IS UNSAFE')],
      'information': [
        (box(30,23,190,91,'#244653',18)+text(54,55,'LET’S BUILD',19,MINT)+line('M56 75h131m-131 18h87','#4e8b91',4)+line('m74 114-10 20 35-20',MINT,3)+box(210,87,115,65,'#193740',14)+dot(240,119,6,PEACH)+dot(268,119,6,PEACH)+dot(296,119,6,PEACH),'IDEAS + QUESTIONS + CONTRIBUTIONS'),
        (document(53,22,'LICENCE')+line('M143 80h46',MINT,2,True)+playfield(214,11)+check(151,133),'CLEAR TERMS FOR YOUR BUILD'),
        (browser(25,20,220,124)+text(45,61,'YOUR CHOICE',16,MINT)+box(47,83,123,31,'#244653',15)+dot(150,98,11,PEACH)+box(242,78,83,67,'#193740',12)+line('M258 78V61a25 25 0 0 1 50 0v17',MINT,5)+dot(283,105,6,PEACH)+line('M283 111v12',PEACH,3),'BROWSER CHOICES + LOCAL MACHINE DATA')],
      'platform': [
        (chip(131,43,'Pi',85,76)+line('M131 78H92V38H65m27 40v51H65')+dot(52,38,12,MINT)+text(39,133,'+100',16,PEACH)+line('M225 78h32')+speaker(277,48),'GAME LOGIC + SOUND + MEDIA'),
        (chip(37,43,'ESP32',88,76)+line('M135 79h36v-35h44m-44 35v48h44')+coil(227,28)+dot(254,127,14,MINT)+line('M276 127h28',PEACH,4),'INPUTS + OUTPUTS + COIL LIMITS'),
        (browser(29,19,302,126)+box(47,57,80,69)+line('M61 73h51m-51 17h35m-35 17h44',MINT,3)+box(144,57,76,69)+dot(182,84,15,PEACH)+box(237,57,76,69)+line('M249 109l15-30 14 19 22-25',MINT,3),'CONFIGURE + CREATE + DIAGNOSE')],
      'home': [
        (chip(29,49,'PIN',65)+line('M104 83h40v-37h39m-39 37v40h39')+badge(196,31,'NAME')+badge(196,108,'LIMITS'),'CONNECT AND CONFIGURE'),
        (playfield(39,12)+arrow(145,78,30)+screen(196,26,127,114)+dot(227,63,10,MINT)+line('M214 106l21-22 19 14 39-38',PEACH,3),'CREATE AND PREVIEW'),
        (document(25,25,'CONFIG')+arrow(125,80,26)+chip(168,48,'ESP',65)+line('M243 82h34')+dot(298,82,20,MINT)+line('m285 82 9 9 17-22','#142b38',4),'DEPLOY AND REFINE')],
      'start-building': [
        (browser(40,18,278,129)+box(57,53,78,76)+line('M69 70h52m-52 20h39m-39 20h46',MINT,3)+box(150,53,150,76)+dot(224,89,22,PEACH),'AUTHOR IN YOUR BROWSER'),
        (box(79,23,201,121,'#244653')+chip(125,48,'Pi',63,60)+box(241,37,31,29,'#355568',3)+box(241,82,31,45,'#355568',3)+line('M94 34h117',PEACH,6)+box(99,114,67,20,'#355568',3),'THE RASPBERRY PI HOST'),
        (box(105,18,150,132,'#244653')+box(128,39,104,66,'#355568')+text(145,78,'ESP32',18,MINT)+box(157,128,47,22,'#355568',3)+line('M117 34v96m126-96v96',PEACH,5)+line('M154 26h46','#4e8b91',3),'THE REAL-TIME CONTROLLER')],
      'kit': [
        (chip(104,38,'Pi',98,81)+box(28,46,47,65,'#355568',4)+text(34,82,'SD',14)+line('M76 79h18')+line('M213 80h36v42h45',PEACH,4)+box(290,108,30,28,'#355568',3),'HOST + STORAGE + POWER'),
        (chip(47,38,'ESP32',92,83)+line('M149 81h42q20 0 20 22t20 22h25',MINT,4)+box(259,110,43,29,'#355568',3)+line('M302 118h14m-14 13h14',PEACH,4),'CONTROLLER + DATA USB CABLE'),
        (browser(25,22,210,117)+line('M44 66h73m-73 20h45',MINT,3)+dot(272,63,23,PEACH)+line('M261 91h23m-19 10h15','#4e8b91',4)+line('M272 27V17m33 28 9-6m-74 6-9-6',MINT,3),'A BROWSER AND YOUR IDEA')],
      'first-steps': [
        (document(22,25,'OS')+arrow(124,81,31)+chip(176,44,'Pi',83)+text(281,88,'>_',24,MINT),'INSTALL THE HOST SOFTWARE'),
        (chip(26,43,'PI',70)+line('M106 79h105',MINT,4)+box(139,66,36,26,'#355568',3)+chip(231,43,'ESP',84)+dot(300,55,5,MINT),'CONNECT AND CHECK ESPLink'),
        (dot(50,80,20,PEACH)+line('M75 81h44v-33h43m-43 33v39h43')+badge(178,33,'SWITCH')+badge(178,105,'LEFT BTN'),'NAME YOUR FIRST COMPONENT'),
        (badge(18,61,'INPUT')+arrow(119,76,20)+dot(170,76,17,MINT)+line('M189 76h37v-30h27m-27 30v45h27')+dot(278,45,17,PEACH)+text(259,133,'+100',18,MINT),'CREATE A LIGHT OR SCORE RESPONSE')],
    }


def illustration(slug, index):
    drawing, label = drawings()[slug][index]
    return ('<svg class="benefit-art" viewBox="0 0 360 190" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">'
            '<g font-family="monospace" font-size="11" fill="#abc0cf">'+drawing+
            f'<text x="180" y="179" text-anchor="middle" fill="{MINT}" font-size="10">{escape(label)}</text></g></svg>')
