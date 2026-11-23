import pandas as pd, numpy as np, sys
D=sys.argv[1]
r=pd.read_csv(f"{D}/routes.txt"); s=pd.read_csv(f"{D}/stops.txt"); t=pd.read_csv(f"{D}/trips.txt")
st=pd.read_csv(f"{D}/stop_times.txt"); sh=pd.read_csv(f"{D}/shapes.txt"); cal=pd.read_csv(f"{D}/calendar.txt")
def sec(x):
    h,m,s_=map(int,x.split(':')); return h*3600+m*60+s_
st['arr']=st.arrival_time.map(sec); st['dep']=st.departure_time.map(sec)
st=st.sort_values(['trip_id','stop_sequence'])
print("calendar end:",cal.end_date.max())
print("trips by service:",t.service_id.value_counts().to_dict())
# monotonic
g=st.groupby('trip_id')
bad=(st.groupby('trip_id').arr.diff()<0).sum(); print("negative time steps:",bad)
print("dwell<0:",(st.dep<st.arr).sum())
# speeds
st2=st.merge(s[['stop_id','stop_lat','stop_lon']],on='stop_id')
st2=st2.sort_values(['trip_id','stop_sequence'])
st2['d']=st2.groupby('trip_id').shape_dist_traveled.diff(); st2['dt']=st2.groupby('trip_id').arr.diff()-0
st2['dt']=st2.arr-st2.groupby('trip_id').dep.shift()
seg=st2.dropna(subset=['d'])
seg=seg[seg.dt>0]; v=seg.d/seg.dt*3.6
print("segment speed km/h pct 1/50/99/max:",np.percentile(v,[1,50,99]).round(1),v.max().round(1))
print("zero/neg travel segs:",((st2.dt<=0)&st2.d.notna()).sum())
# unused stops / stops far from shape
used=set(st.stop_id); print("unused stops:",len(set(s.stop_id)-used), s[~s.stop_id.isin(used)].stop_name.tolist())
# per-route summary weekday
tw=t[t.service_id=='weekday']
first=st.groupby('trip_id').agg(start=('dep','min'),end=('arr','max'),n=('stop_id','size')).reset_index()
x=tw.merge(first,on='trip_id').merge(r[['route_id','route_short_name','route_long_name']],on='route_id')
x['dur']=(x.end-x.start)/60
def hw(df,h0,h1):
    d=np.sort(df.start[(df.start>=h0*3600)&(df.start<h1*3600)].values)
    return round(np.median(np.diff(d))/60,1) if len(d)>2 else None
rows=[]
for k,df in x.groupby(['route_short_name','route_long_name']):
    rows.append(dict(route=k[0],name=k[1][:45],trips=len(df),first=f"{int(df.start.min()//3600):02d}:{int(df.start.min()%3600//60):02d}",last=f"{int(df.start.max()//3600):02d}:{int(df.start.max()%3600//60):02d}",dur_min=round(df.dur.median(),1),stops=int(df.n.median()),hw_peak=hw(df,8,10),hw_mid=hw(df,12,15),hw_eve=hw(df,21,23)))
out=pd.DataFrame(rows).sort_values('route'); print(out.to_string(index=False))
out.to_csv('route_summary.csv',index=False)
# shape sanity
shp=sh.groupby('shape_id').agg(pts=('shape_pt_sequence','size'),len_km=('shape_dist_traveled','max')); shp['len_km']/=1000
print(shp.describe().round(2))
print("trips sharing shapes:",t.shape_id.nunique(),"shapes",sh.shape_id.nunique())
# max simultaneous trains weekday
times=np.arange(5*3600,24*3600,60)
active=[((first.start<=tt)&(first.end>=tt)&first.trip_id.isin(tw.trip_id)).sum() for tt in times]
i=int(np.argmax(active)); print("peak trains in service:",max(active),"at",times[i]//3600,":",times[i]%3600//60)
# --- after the build: check data.json (python3 scripts/audit.py GTFS_DIR [data.json]) ---
import json, math, os
J = sys.argv[2] if len(sys.argv) > 2 else 'data.json'
if os.path.exists(J):
    dj = json.load(open(J)); S = dj['stops']
    def hvm(a, b):
        p1, p2 = math.radians(a[1]), math.radians(b[1]); dl = math.radians(b[0] - a[0])
        return 2 * 6371008.8 * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
    KX = math.cos(math.radians(28.62))
    def segd(pt, a, b):  # metres from pt to segment ab (local flat approximation)
        ax, ay, bx, by, px, py = a[0] * KX, a[1], b[0] * KX, b[1], pt[0] * KX, pt[1]
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
        return math.hypot(ax + dx * u - px, ay + dy * u - py) * 111195
    vs, off, back, hp = [], [], 0, []
    for ro in dj['routes']:
        p = ro['pat']
        vs += [(b[3] - a[3]) / (b[1] - a[2]) * 3.6 for a, b in zip(p, p[1:]) if b[1] > a[2]]
        for q in p:
            s_ = S[str(q[0])][1:]; off.append(min(segd(s_, a, b) for a, b in zip(ro['shape'], ro['shape'][1:])))
        sh_ = ro['shape']
        for a, b, c in zip(sh_, sh_[1:], sh_[2:]):
            v1 = (a[0] - b[0], a[1] - b[1]); v2 = (c[0] - b[0], c[1] - b[1])
            if v1[0] * v2[0] + v1[1] * v2[1] > 0.9 * math.hypot(*v1) * math.hypot(*v2): back += 1; hp.append(ro['id'])
    print(f"data.json: {len(dj['routes'])} routes ({sum(1 for x in dj['routes'] if x.get('est'))} estimated), {len(S)} stops")
    print("data.json segment speed km/h pct 1/50/99/max:", np.percentile(vs, [1, 50, 99]).round(1), round(max(vs), 1))
    print("data.json stop to shape m, median/90%/max:", round(float(np.median(off))), round(float(np.percentile(off, 90))), round(max(off)))
    print("data.json shape hairpins (<26 deg):", back, sorted(set(hp)))
    print("data.json build fixes:", len(dj.get('meta', {}).get('fixes', [])))
