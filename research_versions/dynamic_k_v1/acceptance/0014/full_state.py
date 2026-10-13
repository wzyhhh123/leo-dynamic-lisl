"""Versioned typed object-graph audit codec, not a checkpoint decoder."""
import hashlib,json,types
from pathlib import Path
from collections import defaultdict,deque
from fractions import Fraction
import numpy as np
from sgp4.api import Satrec
SCHEMA='dynamic_k_p0e_complete_python_graph_with_native_recipe_v1'
def dumps(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def sha(x):return hashlib.sha256(dumps(x).encode('utf-8')).hexdigest()
def qualified(x):return x.__module__+'.'+x.__qualname__
def capture(root):
    memo={};objects=[]
    def walk(x):
        t=type(x)
        if x is None:return ['none']
        if t is bool:return ['bool',x]
        if t is int:return ['int',str(x)]
        if t is float:return ['float64',x.hex()]
        if t is str:return ['str',x]
        if t is bytes:return ['bytes',x.hex()]
        if isinstance(x,Fraction):return ['fraction',str(x.numerator),str(x.denominator)]
        if isinstance(x,Path):return ['path',qualified(t),str(x)]
        if isinstance(x,type):return ['class',qualified(x)]
        if isinstance(x,np.generic):return ['numpy_scalar',str(x.dtype),x.tobytes().hex()]
        if callable(x) and isinstance(x,(types.FunctionType,types.BuiltinFunctionType)):
            return ['callable',qualified(x)]
        ident=id(x)
        if ident in memo:return ['ref',memo[ident]]
        index=len(objects);memo[ident]=index;objects.append(None)
        if isinstance(x,Satrec):
            # Native hidden state is reproduced by the pinned TLE+binary+call recipe.
            # All exposed native scalar state is audited here, never overwritten.
            state=[]
            for k in sorted(dir(x)):
                if k.startswith('_'):continue
                v=getattr(x,k)
                if callable(v):continue
                state.append([k,walk(v)])
            node=dict(type=qualified(t),native='SGP4_REBUILT_BY_BOUND_EXECUTABLE_RECIPE',fields=state)
        elif isinstance(x,defaultdict):node=dict(type=qualified(t),factory=walk(x.default_factory),items=[[walk(k),walk(v)] for k,v in x.items()])
        elif isinstance(x,dict):node=dict(type=qualified(t),items=[[walk(k),walk(v)] for k,v in x.items()])
        elif isinstance(x,(list,tuple,set,frozenset,deque)):
            node=dict(type=qualified(t),items=[walk(v) for v in x])
            if isinstance(x,deque):node['maxlen']=walk(x.maxlen)
        elif isinstance(x,np.ndarray):
            if x.dtype.hasobject:raise ValueError('OBJECT_ARRAY_NOT_SUPPORTED')
            node=dict(type=qualified(t),dtype=x.dtype.str,shape=list(x.shape),strides=list(x.strides),
                      c_contiguous=bool(x.flags.c_contiguous),f_contiguous=bool(x.flags.f_contiguous),
                      data_C_hex=x.tobytes(order='C').hex())
        elif hasattr(x,'__dict__'):node=dict(type=qualified(t),fields=[[k,walk(v)] for k,v in vars(x).items()])
        else:raise ValueError('UNSUPPORTED_FULL_STATE:'+qualified(t))
        objects[index]=node
        return ['ref',index]
    handle=walk(root)
    return dict(schema=SCHEMA,root=handle,objects=objects)
def first_diff(a,b,path='$'):
    if type(a) is not type(b):return dict(path=path,expected=a,actual=b)
    if isinstance(a,dict):
        if list(a)!=list(b):
            if set(a)!=set(b):return dict(path=path+'.keys',expected=list(a),actual=list(b))
        for k in a:
            d=first_diff(a[k],b[k],path+'.'+k)
            if d:return d
    elif isinstance(a,list):
        if len(a)!=len(b):return dict(path=path+'.length',expected=len(a),actual=len(b))
        for i,(x,y) in enumerate(zip(a,b)):
            d=first_diff(x,y,path+'['+str(i)+']')
            if d:return d
    elif a!=b:return dict(path=path,expected=a,actual=b)
    return None
