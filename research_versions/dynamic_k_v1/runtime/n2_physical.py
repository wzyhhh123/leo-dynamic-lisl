"""N2 physical guard and clone-safe SGP4 adapter; frozen kernels unchanged."""
from copy import deepcopy
import numpy as np
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.sgp4_geometry import margins
from dynamic_lisl.gate_c_terminal_geometry import bilateral_for


class ReplayableSgp4Model(Sgp4Model):
    def __deepcopy__(self,memo):
        result=type(self)(deepcopy(self.records,memo),self.duration_s)
        memo[id(self)]=result
        return result


class Sgp4PhysicalGuard:
    scope='FROZEN_SYNTHETIC_TLE_REAL_SGP4_GEOMETRY'
    def __init__(self,model,config,*,earth_radius_km):
        if not np.isfinite(earth_radius_km) or earth_radius_km<=0:raise ValueError('INVALID_EARTH_RADIUS')
        self.model,self.config,self.earth_radius_km=model,config,float(earth_radius_km)

    def evaluate(self,a,b,t):
        r,v=self.model.state([t],(a[0],b[0]))
        los=float(margins(r,np.inf,self.earth_radius_km)[0])
        if los<0:return dict(accepted=False,reason='LOS_BLOCKED',los_margin_km=los)
        result=bilateral_for(r[0,0],v[0,0],a[1],r[0,1],v[0,1],b[1],self.config)
        return dict(accepted=result['feasible'],reason=result['reason'],los_margin_km=los,for_details=result)


class SyntheticWindowGuard:
    """Explicit engineering fixture: supplied windows stand for filtered LOS/FoR."""
    scope='ENGINEERING_SYNTHETIC_PRE_FILTERED_WINDOWS'
    def __init__(self,rejections=None):self.rejections=dict(rejections or {})
    def evaluate(self,a,b,t):
        reason=self.rejections.get(tuple(sorted((tuple(a),tuple(b)))))
        return dict(accepted=reason is None,reason=reason)


class N2PhysicalLayer:
    def __init__(self,gate_c,guard):self.gate_c,self.guard=gate_c,guard
    @property
    def catalog(self):return self.gate_c.catalog

    def evaluate(self,executor,a,b,setup,release_after=()):
        try:
            live=self.guard.evaluate(a,b,executor.now)
            if not live['accepted']:return dict(accepted=False,reason=live['reason'],live_geometry=live)
            result=self.gate_c.evaluate(executor,a,b,retarget_a=setup.retarget_a_s,
                retarget_b=setup.retarget_b_s,acquisition=setup.acquisition_s,release_after=release_after)
            if not result['accepted']:return result
            ready=self.guard.evaluate(a,b,result['geometry']['ready_time'])
            if not ready['accepted']:return dict(accepted=False,reason='READY_'+ready['reason'],live_geometry=ready)
            return dict(result,live_geometry=live,ready_geometry=ready,geometry_scope=self.guard.scope)
        except (KeyError,ValueError) as error:
            return dict(accepted=False,reason='GEOMETRY_INPUT_INVALID',detail=str(error))
