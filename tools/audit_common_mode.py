"""Read-only common-mode/structural geometry sensitivity audit; no new orbit asset."""
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.sgp4_geometry import search_windows,margins
from dynamic_lisl.common import PROJECT,new_output,dump,sha

def metric(x):
 x=np.asarray(x);return dict(max_abs=float(np.max(abs(x))),rms=float(np.sqrt(np.mean(x*x))),mean=float(np.mean(x)))
def wrap(x):return (x+180)%360-180
def angles(r,v):
 h=np.cross(r,v);h/=np.linalg.norm(h,axis=1)[:,None];n=np.cross(np.tile([0.,0.,1.],(len(r),1)),h);n/=np.linalg.norm(n,axis=1)[:,None]
 return np.c_[np.degrees(np.arctan2(n[:,1],n[:,0])),np.degrees(np.arccos(h[:,2])),np.degrees(np.arctan2(np.sum(r*np.cross(h,n),axis=1),np.sum(r*n,axis=1)))]
def decomposition(a,target):
 e=wrap(a-target);result={}
 for k,name in enumerate(['raan','inclination','phase']):
  bias=float(np.mean(e[:,k]));result[name]=dict(common_bias_deg=bias,residual_deg=metric(e[:,k]-bias))
 a=a.reshape(18,40,3)
 result['relative_raan_adjacent_planes_deg']=metric(wrap(a[1:,:,0]-a[:-1,:,0]-10))
 result['intra_plane_phase_9deg_residual_deg']=metric(wrap(np.roll(a[:,:,2],-1,axis=1)-a[:,:,2]-9))
 result['inter_plane_phase_0p5deg_residual_deg']=metric(wrap(a[1:,:,2]-a[:-1,:,2]-.5))
 result['within_plane_raan_spread_deg']=metric(wrap(a[:,:,0]-np.mean(a[:,:,0],axis=1)[:,None]))
 return result

def main():
 model=Sgp4Model.load(PROJECT/'data/raw/sgp4_x720');out=new_output('common_mode_audit');r,v=model.state(0);r=r[0];v=v[0]
 planes=np.array([x['plane_id'] for x in model.records]);slots=np.array([x['slot_id'] for x in model.records]);assert np.array_equal(planes,np.repeat(np.arange(18),40)) and np.array_equal(slots,np.tile(np.arange(40),18))
 target=np.c_[planes*10,np.full(720,85),slots*9+planes*.5];O,I,U=np.radians(target).T
 n=np.c_[np.cos(O),np.sin(O),np.zeros(720)];h=np.c_[np.sin(I)*np.sin(O),-np.sin(I)*np.cos(O),np.cos(I)];q=np.cross(h,n)
 er=n*np.cos(U)[:,None]+q*np.sin(U)[:,None];et=np.cross(h,er);T=np.stack([er,et,h],axis=2)
 ar=r/np.linalg.norm(r,axis=1)[:,None];ah=np.cross(r,v);ah/=np.linalg.norm(ah,axis=1)[:,None];A=np.stack([ar,np.cross(ah,ar),ah],axis=2)
 uu,ss,vt=np.linalg.svd(np.einsum('nik,njk->ij',A,T));R=uu@np.diag([1,1,np.linalg.det(uu@vt)])@vt
 desired=np.einsum('ij,njk->nik',R,T);C=np.einsum('nik,njk->nij',desired,A)
 aligned_r=r@R;aligned_v=v@R
 result=dict(raw=decomposition(angles(r,v),target),after_best_rigid_rotation=decomposition(angles(aligned_r,aligned_v),target),rotation_target_to_actual=R.tolist(),rotation_angle_deg=float(np.degrees(np.arccos(np.clip((np.trace(R)-1)/2,-1,1)))),epoch_position_residual_km=metric(np.linalg.norm(aligned_r-er*np.linalg.norm(r,axis=1)[:,None],axis=1)),method='One proper orthogonal rotation fitted equally to 720 radial/tangential/normal unit triads. Structural counterfactual rotates each entire SGP4 trajectory by its epoch triad correction, preserving radial history. Kinematic sensitivity only, NOT a new SGP4 orbit or a replacement asset.')
 times=np.arange(0,601,30.);rr,_=model.state(times);projected=np.einsum('nij,tnj->tni',C,rr);ii,jj=np.triu_indices(720,1);snaps=[]
 for k,t in enumerate(times):
  x=rr[k,np.stack([ii,jj],axis=1)];y=projected[k,np.stack([ii,jj],axis=1)];rot=x@R
  ma=margins(x,5000,6378.137);mb=margins(y,5000,6378.137);mr=margins(rot,5000,6378.137);aa=ma>0;bb=mb>0
  snaps.append(dict(time_s=float(t),actual=int(aa.sum()),projected=int(bb.sum()),symmetric_difference=int((aa^bb).sum()),jaccard=float((aa&bb).sum()/(aa|bb).sum()),rigid_rotation_candidate_changes=int((aa!=(mr>0)).sum()),rigid_margin_error_km=float(np.max(abs(ma-mr))),pair_distance_change_km=metric(np.linalg.norm(y[:,1]-y[:,0],axis=1)-np.linalg.norm(x[:,1]-x[:,0],axis=1))))
 result['snapshots']=snaps;dump(out/'preliminary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='snapshots'},indent=2),flush=True)
 parent=PROJECT/'outputs/visibility_20260921T055451_308214Z';old={}
 for line in (parent/'intervals.jsonl').read_text().splitlines():
  w=json.loads(line);old.setdefault((w['i'],w['j']),[]).append((w['start_s'],w['end_s']))
 changes=[];shifts=[];unstable=[];totaldiff=0.;totalold=0.;newcount=0;grazing=[]
 for i in range(720):
  for j in range(i+1,720):
   def state(t):return np.einsum('nij,tnj->tni',C[[i,j]],model.state(t,[model.ids[i],model.ids[j]])[0])
   a=search_windows(state,0,600,5000,scan_step_s=30);b=search_windows(state,0,600,5000,scan_step_s=15)
   if len(a['roots_s'])!=len(b['roots_s']) or max((abs(x-y) for x,y in zip(a['roots_s'],b['roots_s'])),default=0)>.01 or [w['state'] for w in a['intervals']]!=[w['state'] for w in b['intervals']]:unstable.append([i,j])
   if a['grazing_regions_s'] or b['grazing_regions_s']:grazing.append([i,j])
   nw=[(w['start_s'],w['end_s']) for w in b['intervals'] if w['state']=='visible'];ow=old.get((i,j),[]);newcount+=len(nw)
   oldtime=sum(y-x for x,y in ow);newtime=sum(y-x for x,y in nw);intersection=sum(max(0,min(b,d)-max(a,c)) for a,b in ow for c,d in nw);diff=max(0,oldtime+newtime-2*intersection);totaldiff+=diff;totalold+=oldtime
   if len(nw)!=len(ow):changes.append(dict(pair=[i,j],old=ow,projected=nw))
   elif ow:
    for ab,cd in zip(ow,nw):
     for x,y in zip(ab,cd):
      if 0<x<600 and 0<y<600:shifts.append(y-x)
  if (i+1)%40==0:print('Completed satellites',i+1,flush=True)
 result['visibility']=dict(projected_interval_count=newcount,interval_count_changed_pairs=changes,matched_interior_boundary_shift_s=metric(shifts),matched_boundaries=len(shifts),symmetric_difference_pair_seconds=totaldiff,actual_visible_pair_seconds=totalold,relative_symmetric_difference=totaldiff/totalold,unstable_pairs=unstable,grazing_pairs=grazing)
 result['source_hashes']={str(p.relative_to(PROJECT)):sha(p) for p in [PROJECT/'data/raw/sgp4_x720/constellation.tle',parent/'intervals.jsonl',Path(__file__)]}
 dump(out/'audit.json',result);dump(out/'hashes.json',{'audit.json':sha(out/'audit.json')});print('OUTPUT',out,flush=True)
if __name__=='__main__':main()
