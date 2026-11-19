"""Draw the proposed isolated-pad interface board and check its connection schedule.

Coordinates are a design grid, not the unverified kit's printed hole labels.
Run from any directory. Requires rsvg-convert; no PCB fabrication is implied.
"""
from pathlib import Path
import html
import math
import subprocess

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT.parents[2] / "assets/docs/media"
PITCH = 2.54
COLS = "ABCDEFGHIJKLMNOPQRSTUVWX"
BUTTONS = ["Start", "Fire", "Lock", "Ramp", "Orbit", "Target", "Bump 1", "Bump 2", "Left flipper", "Right flipper"]
BUTTON_COLS = "BDFHJLNPRT"
U1 = dict(zip(range(1, 8), [f"{c}14" for c in "CDEFGHI"]))
U1.update(dict(zip(range(14, 7, -1), [f"{c}11" for c in "CDEFGHI"])))
U2 = dict(zip(["HV1", "HV2", "HV", "HGND", "HV3", "HV4"], [f"{c}10" for c in "NOPQRS"]))
U2.update(dict(zip(["LV1", "LV2", "LV", "LGND", "LV3", "LV4"], [f"{c}14" for c in "NOPQRS"])))
RESISTORS = [(f"R{i}", "4.7k", f"{c}2", f"{c}6") for i, c in enumerate(BUTTON_COLS, 1)]
RESISTORS += [("R11", "10k", "K11", "K12"), ("R12", "10k", "K14", "K15"), ("R13", "10k", "A12", "A13"), ("R14", "330", "V12", "V13")]
CAPS = [("C1", "100nF", "C9", "D9"), ("C2", "470uF", "V2", "X2"), ("C3", "470uF", "V7", "X7")]
NETS = {
    "3V3": [f"{c}2" for c in BUTTON_COLS] + ["P14", "P15"],
    "GND": ["D9", "C14", "G14", "I14", "E11", "H11", "K12", "K15", "A13", "X2", "X7", "X11", "X12", "Q10", "Q9", "Q14", "Q15", "A8"],
    "5V_LED": ["V2", "V7", "X10", "C9", "C11", "D11", "F14", "G11"],
    "5V_LOGIC": ["M9", "P9", "P10"],
    "LED_IN": ["A11", "A12", "D14"],
    "LED_BUFFER": ["E14", "V12"],
    "LED_DIN": ["V13", "X13"],
    "LAMP_L": ["K9", "K10", "K11"],
    "LAMP_R": ["K14", "K16", "L16"],
    "SDA_3V3": ["N14", "N15"], "SCL_3V3": ["O14", "O15"],
    "SDA_5V": ["N9", "N10"], "SCL_5V": ["O9", "O10"],
}
for i, c in enumerate(BUTTON_COLS, 1):
    NETS[f"BTN{i:02}"] = [f"{c}6", f"{c}7", f"{c}8"]
NC = [U1[p] for p in (6, 8, 11)] + [U2[p] for p in ("HV3", "HV4", "LV3", "LV4")]
PALETTE = {"3V3": "#ad4db0", "GND": "#35434b", "5V_LED": "#d45832", "5V_LOGIC": "#c58b05", "LED_IN": "#367ac0", "LED_BUFFER": "#168878", "LED_DIN": "#168878", "LAMP_L": "#a56c2b", "LAMP_R": "#a56c2b"}


def point(pad):
    return 5.79 + COLS.index(pad[0]) * PITCH, 5.95 + (int(pad[1:]) - 1) * PITCH


def validate():
    assignments = {}
    for net, pads in NETS.items():
        for pad in pads:
            assert pad not in assignments, (pad, net, assignments.get(pad))
            assignments[pad] = net
            x, y = point(pad)
            assert 0 < x < 70 and 0 < y < 50
    occupied = []
    for _, _, a, b in RESISTORS + CAPS:
        occupied.extend([a, b])
        assert a in assignments and b in assignments
        assert assignments[a] != assignments[b]
    occupied += list(U1.values()) + list(U2.values())
    assert len(occupied) == len(set(occupied)), "Two component leads share a hole"
    assert all(p in assignments or p in NC for p in occupied)
    assert not set(NC) & set(assignments)
    assert len(RESISTORS) == 14 and len(CAPS) == 3
    expected = {1: "GND", 2: "LED_IN", 3: "LED_BUFFER", 4: "5V_LED", 5: "GND", 7: "GND", 9: "GND", 10: "5V_LED", 12: "GND", 13: "5V_LED", 14: "5V_LED"}
    assert all(assignments[U1[p]] == n for p, n in expected.items())
    assert assignments[U2["HV"]] == "5V_LOGIC" and assignments[U2["LV"]] == "3V3"
    assert assignments[U2["HGND"]] == assignments[U2["LGND"]] == "GND"
    for c in BUTTON_COLS:
        assert assignments[c + "2"] == "3V3"
        assert assignments[c + "6"] == assignments[c + "7"] == assignments[c + "8"]
    print("PASS: 14 resistors, 3 capacitors, 14 IC pins, 12 module pins; unique lead holes and net assignments.")
    print("PASS: unused outputs isolated; 5V_LED, 5V_LOGIC and 3V3 are separate nets.")
    print("LIMIT: connectivity intent only; not a solder inspection, manufacturer footprint or tested circuit.")


class SVG:
    def __init__(self, width, height, title, subtitle):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Arial, sans-serif">']
        self.rect(0, 0, width, height, "#f6f8f9", "none")
        self.text(42, 52, title, 29, "#203541")
        self.text(42, 85, subtitle, 17, "#526671")

    def rect(self, x, y, w, h, fill, stroke="#71818a", radius=0):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(self, x, y, text, size=16, color="#203541", anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" text-anchor="{anchor}">{html.escape(str(text))}</text>')

    def line(self, x, y, xx, yy, color="#526671", width=1.5, dashed=False):
        self.parts.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{color}" stroke-width="{width}"' + (' stroke-dasharray="6 5"' if dashed else '') + '/>')

    def circle(self, x, y, r, fill, stroke="#71818a"):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}"/>')

    def save(self, name):
        path = ROOT / f"{name}.svg"
        path.write_text("\n".join(self.parts + ["</svg>"]))
        subprocess.run(["rsvg-convert", "-o", str(MEDIA / f"{name}.png"), str(path)], check=True)


def board_base(s, mirror=False):
    def xy(pad):
        x, y = point(pad)
        return 60 + (70 - x if mirror else x) * 12, 150 + y * 12
    s.rect(60, 150, 840, 600, "#d7e4d4", "#506d54", 10)
    for c in COLS:
        x, _ = xy(c + "1")
        s.text(x, 137, c, 16, anchor="middle")
        for r in range(1, 17):
            x, y = xy(f"{c}{r}")
            s.circle(x, y, 3.5, "#a4b29e", "#8a9a84")
    for r in range(1, 17):
        _, y = xy(f"A{r}")
        s.text(39, y + 5, r, 16, anchor="middle")
    for x, y in [(3, 3), (67, 3), (3, 47), (67, 47)]:
        s.circle(60 + (70 - x if mirror else x) * 12, 150 + y * 12, 17, "#f6f8f9")
    s.text(480, 788, "70 mm × 50 mm • 2.54 mm pad pitch", 22, anchor="middle")
    s.text(480, 816, "Four corner fixing zones: actual holes must be measured", 16, anchor="middle")
    return xy


def layout():
    s = SVG(1400, 950, "ONE SOLDERED INTERFACE BOARD", "Component side • proposed 70 × 50 mm board • grid labels are design references")
    xy = board_base(s)
    for name, value, a, b in RESISTORS:
        x, y = xy(a); xx, yy = xy(b)
        s.line(x, y, xx, yy, "#69747b", 4)
        if int(name[1:]) <= 10:
            s.rect(x - 12, (y + yy) / 2 - 35, 24, 70, "#a4d6e8", "#47738b", 6)
            s.text(x, y - 13, name, 12, anchor="middle")
        else:
            s.circle(x, y, 12, "#a4d6e8", "#47738b")
            s.text(x + 17, y - 8, name, 12)
    for i, c in enumerate(BUTTON_COLS, 1):
        for row in (7, 8):
            x, y = xy(c + str(row)); s.circle(x, y, 6, "#e7ab45", "#8a6937")
        x, y = xy(c + "8"); s.text(x, y + 20, i, 12, anchor="middle")
    # DIP14 horizontal: notch LEFT, pin 1 at bottom-left.
    x, y = xy("C11"); xx, yy = xy("I14")
    s.rect(x - 23, y + 8, xx - x + 46, yy - y - 16, "#26343b", "#111c22", 7)
    s.circle(x - 21, (y + yy) / 2, 12, "#d7e4d4", "#d7e4d4")
    s.text((x + xx) / 2, (y + yy) / 2 - 5, "U1", 18, "#fff", "middle")
    s.text((x + xx) / 2, (y + yy) / 2 + 18, "74AHCT125", 14, "#fff", "middle")
    for p, pad in U1.items():
        x, y = xy(pad); s.rect(x - 5, y - 5, 10, 10, "#d6dde0")
        s.text(x, y - 12 if p >= 8 else y + 22, p, 11, anchor="middle")
    x, y = xy("N10"); xx, yy = xy("S14")
    s.rect(x - 14, y - 17, xx - x + 28, yy - y + 34, "#447ba4", "#275371", 4)
    for name, pad in U2.items():
        x, y = xy(pad); s.circle(x, y, 6, "#dfe2d1")
        s.text(x, y + 19 if "10" in pad else y - 13, name.replace("HGND", "G").replace("LGND", "G"), 10, "#fff", "middle")
    s.text(*xy("P12"), "U2 • I²C", 14, "#fff", "middle")
    for name, value, a, b in CAPS:
        x, y = xy(a); xx, _ = xy(b)
        if name == "C1":
            s.rect(x - 7, y - 12, xx - x + 14, 24, "#d9a661", "#976f36", 8)
            s.text(x - 10, y - 22, "C1 · 100 nF", 12)
        else:
            s.circle((x + xx) / 2, y, 60, "#45535a", "#25363e")
            s.circle((x + xx) / 2, y, 49, "#d6dadd", "#6e7d85")
            s.text((x + xx) / 2, y - 3, name, 16, anchor="middle")
            s.text((x + xx) / 2, y + 18, "470 µF", 13, anchor="middle")
            s.text(x - 12, y + 12, "+", 18, "#e45e32")
            s.text(xx + 12, y + 12, "−", 18)
    items = [
        ("R1–R10", "10 × 4.7 kΩ button pull-ups"),
        ("R11 / R12", "10 kΩ lamp-input pull-downs"),
        ("R13", "10 kΩ LED-input pull-down"),
        ("R14", "330 Ω LED data resistor"),
        ("U1 / C1", "LED buffer + 100 nF bypass"),
        ("U2", "13 × 15 mm LCD I²C module"),
        ("C2 / C3", "470 µF / 16 V, each ≤Ø10 × 16"),
    ]
    for i, (title, detail) in enumerate(items):
        s.text(945, 170 + i * 62, title, 19)
        s.text(945, 195 + i * 62, detail, 16)
    s.text(945, 633, "Labelled soldered leads", 20)
    s.text(945, 661, "Row 7: ESP button signals", 17)
    s.text(945, 688, "Row 8: button contacts", 17)
    s.text(945, 715, "R11–R14 stand upright", 17)
    s.text(42, 874, "Use isolated copper pads, not connected stripboard. No solderless breadboard or extra PCB is installed.", 19)
    s.text(42, 909, "Provisional: verify 24 × 16 usable holes, module row spacing, capacitor sizes and corner fixing clearance.", 19, "#945015")
    s.save("bench-interface-layout-v1")


def solder():
    s = SVG(1400, 1050, "SOLDER SIDE / CONNECTION MAP", "Viewed from BELOW • letters run X → A • flip left-to-right, never copy the top view unchanged")
    xy = board_base(s, True)
    # Minimum spanning trees keep links short. These are connectivity guides;
    # insulated wire can cross, with no joint except at marked endpoint pads.
    for name, pads in NETS.items():
        color = PALETTE.get(name, "#377d98")
        done, todo = [pads[0]], pads[1:]
        while todo:
            if name == "GND" and len(done) == 1:
                a, b = "D9", "I14"  # C1 return directly to U1 ground pin.
            else:
                _, a, b = min((math.dist(point(a), point(b)), a, b) for a in done for b in todo)
            ax, ay = xy(a); bx, by = xy(b)
            # Route long jumpers between grid lines, so an insulated wire does
            # not appear to terminate on an unrelated component pad en route.
            if math.dist(point(a), point(b)) > 5.09:
                offset = {"GND": -10, "3V3": 10, "5V_LED": 7, "LED_IN": -7, "LED_BUFFER": -12}.get(name, 12)
                route = [(ax, ay), (ax + offset, ay), (ax + offset, by + offset), (bx, by + offset), (bx, by)]
                for start, end in zip(route, route[1:]):
                    s.line(*start, *end, color, 2.5)
            else:
                s.line(ax, ay, bx, by, color, 2.5)
            done.append(b); todo.remove(b)
        for p in pads:
            s.circle(*xy(p), 5.5, color, "#fff")
    for p in NC:
        x, y = xy(p); s.line(x - 5, y - 5, x + 5, y + 5, "#aa2932", 2)
        s.line(x - 5, y + 5, x + 5, y - 5, "#aa2932", 2)
    for i, (name, color) in enumerate(PALETTE.items()):
        s.line(950, 170 + i * 40, 980, 170 + i * 40, color, 4)
        s.text(995, 176 + i * 40, name, 19)
    s.text(950, 620, "● = solder at this pad", 19)
    s.text(950, 651, "Crossing lines ≠ junction", 19)
    s.text(950, 682, "× = leave unconnected", 19, "#aa2932")
    s.text(950, 730, "Use the net table to verify", 18)
    s.text(950, 758, "every endpoint before power.", 18)
    s.text(42, 874, "Insulated point-to-point links on the copper side; crossings remain insulated. No continuous solder rails implied.", 18)
    s.text(42, 909, "Lead pads are shared by their component and its solder joint, not by two component leads pushed into one hole.", 18)
    s.text(42, 944, "Keep C1 leads short. Keep copper-side wires/solder below 3 mm so the 10 mm panel standoff space stays clear.", 18)
    s.text(42, 982, "No strip or lamp load current through the pad network. LED supply/capacitor spur is wired separately at C2/C3.", 18, "#945015")
    s.save("bench-interface-solder-v1")


def circuit_diagram():
    s = SVG(1500, 1240, "ONE BOARD / ELECTRICAL SCHEMATIC", "Named signals match the pad table • dots are junctions • GND is common throughout")
    def node(x, y): s.circle(x, y, 4, "#203541", "#203541")
    def ground(x, y):
        s.line(x, y, x, y + 9)
        for i, w in enumerate([24, 16, 8]): s.line(x - w / 2, y + 9 + i * 5, x + w / 2, y + 9 + i * 5)
    def res(x, y, text, vertical=False):
        if vertical:
            s.line(x, y, x, y + 15); s.rect(x - 7, y + 15, 14, 40, "#fff")
            s.line(x, y + 55, x, y + 70); s.text(x + 16, y + 39, text, 15)
        else:
            s.line(x, y, x + 15, y); s.rect(x + 15, y - 7, 45, 14, "#fff")
            s.line(x + 60, y, x + 75, y); s.text(x + 37, y - 17, text, 15, anchor="middle")
    def cap(x, y, label, polar=False):
        s.line(x, y, x, y + 25); s.line(x - 13, y + 25, x + 13, y + 25)
        s.line(x - 13, y + 32, x + 13, y + 32); s.line(x, y + 32, x, y + 60)
        s.text(x + 19, y + 47, label, 15)
        if polar: s.text(x - 26, y + 20, "+", 18)
    def panel(x, y, w, h, title):
        s.rect(x, y, w, h, "#fff", "#b1bfc6", 9);s.text(x + 20, y + 33, title, 21)
    panel(40, 115, 690, 275, "BUTTON INPUT — repeat ×10, R1–R10")
    s.text(290, 178, "ESP 3V3", 17, anchor="middle");res(290, 190, "4.7 kΩ", True)
    node(290, 260);s.line(290, 260, 100, 260);s.text(100, 247, "ESP BTNxx", 17)
    s.line(290, 260, 485, 260);s.circle(485, 260, 4, "#fff");s.circle(530, 260, 4, "#fff")
    s.line(485, 260, 523, 239);s.line(530, 260, 580, 260);ground(580, 260)
    s.text(480, 298, "N.O. button", 17);s.text(65, 349, "Row 7 → ESP; row 8 → switch. Pressed = LOW.", 17)
    panel(770, 115, 690, 275, "LAMP CONTROL — repeat ×2, R11 / R12")
    s.line(810, 220, 1405, 220);node(1035, 220);res(1035, 220, "10 kΩ", True);ground(1035, 290)
    s.text(810, 199, "ESP LAMP_L / R", 17);s.text(1190, 199, "P16 control input", 17)
    s.text(795, 355, "P16 must be active-high. Lamp power stays off this board.", 17)
    panel(40, 415, 1420, 430, "LED BUFFER — U1 74AHCT125, powered from 5V_LED")
    s.line(505, 495, 1370, 495, "#d45832", 3);s.text(520, 482, "5V_LED (fused lighting supply)", 17, "#b64827")
    s.rect(470, 540, 220, 160, "#e5f0eb", "#628e7b", 6)
    s.text(580, 573, "U1", 23, anchor="middle");s.text(580, 600, "74AHCT125", 19, anchor="middle")
    s.line(505, 495, 505, 540);node(505, 495);s.text(517, 533, "14 VCC", 15)
    s.line(100, 625, 470, 625);s.text(100, 611, "ESP LED_IN", 17);s.text(481, 630, "2  A1", 16)
    node(300, 625);res(300, 625, "R13 10 kΩ", True);ground(300, 695)
    s.text(624, 630, "Y1  3", 16);s.line(690, 625, 740, 625);res(740, 625, "R14 330 Ω")
    s.line(815, 625, 1240, 625);s.text(900, 650, "Short DIN/GND pair", 16)
    s.rect(1240, 575, 180, 145, "#edf4e9", "#698a60", 6)
    s.text(1257, 605, "FIRST PIXEL", 19);s.text(1257, 635, "DIN", 17)
    s.line(1370, 495, 1370, 575, "#d45832", 3);s.text(1343, 562, "+5V", 15)
    ground(1370, 720);s.text(1300, 703, "GND", 16)
    s.line(505, 700, 505, 725);ground(505, 725);s.text(470, 753, "7 GND", 15)
    s.line(645, 700, 645, 725);ground(645, 725);s.text(604, 753, "1 /OE1", 15)
    for x, label, pol in [(745, "C1 100 nF", False), (925, "C2 470 µF", True), (1100, "C3 470 µF", True)]:
        node(x, 495);cap(x, 495, label, pol);ground(x, 555)
    s.text(65, 794, "Unused: /OE pins 4, 10, 13 → 5V_LED; A pins 5, 9, 12 → GND; Y pins 6, 8, 11 → no connection.", 18)
    s.text(65, 824, "C2/C3 rated 16 V. Strip +5V/GND use the external power wiring; only the capacitor spur and buffer take power here.", 17)
    panel(40, 870, 860, 310, "LCD I²C — U2, use channels 1 / 2")
    s.rect(340, 948, 245, 162, "#e6eef8", "#7991a6", 5)
    for y, low, high, left, right in [(995, "LV1", "HV1", "ESP SDA", "LCD SDA"), (1040, "LV2", "HV2", "ESP SCL", "LCD SCL")]:
        s.line(95, y, 340, y);s.line(585, y, 820, y)
        s.text(95, y - 10, left, 17);s.text(720, y - 10, right, 17)
        s.text(354, y + 6, low, 17);s.text(527, y + 6, high, 17);s.text(460, y + 6, "⇄", 22, anchor="middle")
    s.text(352, 974, "LV", 15);s.text(550, 974, "HV", 15)
    s.line(367, 948, 367, 929);s.text(355, 923, "3V3", 16)
    s.line(561, 948, 561, 929);s.text(550, 923, "5V_LOGIC", 16)
    s.text(460, 1098, "Both GND pins", 16, anchor="middle");ground(460, 1110)
    s.text(63, 1163, "LCD VCC → 5V_LOGIC; LCD GND → GND. Spare channels 3/4: no wires.", 17)
    panel(930, 870, 530, 310, "EXTERNAL CONNECTIONS")
    for i, text in enumerate(["8 receiver signals → ESP INPUT_PULLUP", "16 optical heads → 5V_LOGIC + GND", "10 blue button rings → 12 V bus + return", "2 P16 load outputs → 2 yellow lamps", "ESP 3V3 comes from its USB-fed board", "No USB VBUS connection to this board", "No GPIO numbering is implied"]):
        s.text(950, 936 + i * 32, text, 17)
    s.text(42, 1218, "Apply power only after continuity, polarity and module pin-label checks. This is a proposed circuit, not tested hardware.", 18, "#945015")
    s.save("bench-interface-wiring-v1")


def net_table():
    rows = ["| Net | Join these pads with insulated links |", "| --- | --- |"]
    rows += [f"| {name} | {', '.join(pads)} |" for name, pads in NETS.items()]
    rows += [f"| No connection | {', '.join(NC)} |"]
    return "\n".join(rows)


if __name__ == "__main__":
    validate()
    layout()
    solder()
    circuit_diagram()
    print(net_table())
