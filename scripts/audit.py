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
