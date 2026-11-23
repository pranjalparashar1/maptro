import pandas as pd, json, math
import sys; D=sys.argv[1] if len(sys.argv)>1 else "DMRC_GTFS"
r=pd.read_csv(f"{D}/routes.txt");s=pd.read_csv(f"{D}/stops.txt");t=pd.read_csv(f"{D}/trips.txt")
st=pd.read_csv(f"{D}/stop_times.txt");sh=pd.read_csv(f"{D}/shapes.txt")
f=lambda x:sum(int(a)*b for a,b in zip(x.split(':'),(3600,60,1)))
st['a']=st.arrival_time.map(f);st['d']=st.departure_time.map(f)
st=st.sort_values(['trip_id','stop_sequence'])
col={'RED':'#e2231a','YELLOW':'#f5c400','BLUE':'#1663be','GREEN':'#2f9e44','VIOLET':'#7d3c98','PINK':'#ee5ca4','MAGENTA':'#b0127e','GRAY':'#8d939a','AQUA':'#18b7c9','ORANGE/AIRPORT':'#f08519','RAPID':'#3d7fd1'}
def rdp(pts,eps):
    if len(pts)<3: return pts
    (x1,y1,_),(x2,y2,_)=pts[0],pts[-1]; dx,dy=x2-x1,y2-y1; L=math.hypot(dx,dy) or 1e-12
    dmax,idx=0,0
    for i in range(1,len(pts)-1):
        x,y,_=pts[i]; dd=abs(dy*x-dx*y+x2*y1-y2*x1)/L
        if dd>dmax: dmax,idx=dd,i
    if dmax>eps: return rdp(pts[:idx+1],eps)[:-1]+rdp(pts[idx:],eps)
    return [pts[0],pts[-1]]
routes=[]
for _,ro in r.iterrows():
    tr=t[t.route_id==ro.route_id]
    if tr.empty: continue
    line,name=ro.route_long_name.split('_',1)
    first=st[st.trip_id==tr.trip_id.iloc[0]]
    a0=first.a.min()
    pat=[[int(x.stop_id),int(x.a-a0),int(x.d-a0),round(float(x.shape_dist_traveled))] for x in first.itertuples()]
    starts=sorted(st[st.trip_id.isin(tr.trip_id)].groupby('trip_id').a.min().astype(int).tolist())
    shp=sh[sh.shape_id==tr.shape_id.iloc[0]].sort_values('shape_pt_sequence')
    pts=[(round(x.shape_pt_lon,5),round(x.shape_pt_lat,5),round(x.shape_dist_traveled)) for x in shp.itertuples()]
    pts=rdp(pts,0.00004)
    routes.append(dict(id=ro.route_short_name,line=line,name=name.strip().replace('  ',' '),pat=pat,starts=starts,shape=[list(p) for p in pts],svc=sorted(tr.service_id.unique().tolist())))
stops={int(x.stop_id):[x.stop_name.strip(),round(x.stop_lon,5),round(x.stop_lat,5)] for x in s.itertuples()}
json.dump(dict(colors=col,routes=routes,stops=stops),open('data.json','w'),separators=(',',':'))
import os;print(os.path.getsize('data.json'),len(routes),sum(len(x['shape']) for x in routes))
