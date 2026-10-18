import re, sys, math

path = sys.argv[1]
with open(path, encoding="utf-8", errors="replace") as fh:
    txt = fh.read()

words = []
for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', txt):
    xmin, ymin, xmax, ymax, s = m.groups()
    s = s.strip()
    if s:
        words.append((float(xmin), float(ymin), float(xmax), float(ymax), s))

def cx(w): return (w[0]+w[2])/2
def cy(w): return (w[1]+w[3])/2
def dist(a,b): return math.hypot(cx(a)-cx(b), cy(a)-cy(b))

port_re = re.compile(r'^P[A-G](1[0-5]|[0-9])$')
ports = [w for w in words if port_re.match(w[4])]
pxs=[cx(w) for w in ports]; pys=[cy(w) for w in ports]
x0,x1,y0,y1=min(pxs),max(pxs),min(pys),max(pys)

# 1) port -> pin number: nearest integer(1..144) token within 40pt on same row/col
ints=[w for w in words if re.fullmatch(r'\d{1,3}',w[4]) and 1<=int(w[4])<=144]
port_pin={}
pinnum_tokens=set()
for p in ports:
    best=None;bd=40
    for w in ints:
        if abs(cy(w)-cy(p))<=3 or abs(cx(w)-cx(p))<=3:
            d=dist(w,p)
            if d<bd: bd=d;best=w
    if best:
        port_pin[p[4]]=int(best[4]); pinnum_tokens.add(id(best))

# MCU-perimeter pin-number tokens = those assigned above (dedupe by position)
pinnums=[w for w in ints if id(w) in pinnum_tokens]

# 2) net label -> nearest pin-number token
SKIP=re.compile(r'^(VDD|VSS|VBAT|VDDA|VSSA|VREF\+?|VCAP1|VCAP2|GND|NC|AGND|DGND)$')
def is_ref(s):
    if re.fullmatch(r'[CRLDQUXYJ]\d+[A-Z]?',s):return True
    if re.fullmatch(r'\d+(\.\d+)?(pF|nF|uF|k|R|uH|nH|V|mA|R0)',s,re.I):return True
    if re.fullmatch(r'\d+(\.\d+)?[kR]',s):return True
    if SKIP.match(s):return True
    return False
def is_net(w):
    s=w[4]
    return bool(re.search(r'[A-Za-z]',s)) and not port_re.match(s) and not re.fullmatch(r'\d{1,3}',s) and not is_ref(s)
nets=[w for w in words if is_net(w)]

pin_net={}  # pin number -> list of (dist, net)
for n in nets:
    best=None;bd=45
    for pn in pinnums:
        # net sits at wire end, roughly same row(for L/R pins) or col(T/B); pick nearest number
        if abs(cy(n)-cy(pn))<=3.5 or abs(cx(n)-cx(pn))<=3.5:
            d=dist(n,pn)
            if d<bd: bd=d;best=pn
    if best:
        pin_net.setdefault(int(best[4]),[]).append((round(bd,1),n[4]))

# join
def pk(item):
    m=re.match(r'P([A-G])(\d+)',item[0]);return (m.group(1),int(m.group(2)))
print(f"# ports={len(ports)} pins_mapped={len(port_pin)} nets={len(nets)}")
for port,pin in sorted(port_pin.items(),key=pk):
    cand=sorted(pin_net.get(pin,[]))
    netstr=", ".join(f"{c[1]}({c[0]})" for c in cand[:3]) if cand else ""
    print(f"{port:5} pin={pin:>3}  {netstr}")
