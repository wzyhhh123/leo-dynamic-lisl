"""Windows path-pinned, ALWAYS freshly byte-verified dependency reader.

No positive hash/validation result is cached. Writable pre-existing mmap views
can bypass Windows share modes, so a content-immutable snapshot is NOT claimed.
Only path traversal is amortized while non-reparse ancestor/file handles deny
write/delete opens. All original verification clauses and raw hashes remain.
No global monkeypatch; original guard classes/kernels/files remain untouched.
"""
import ast
import ctypes
from ctypes import wintypes as W
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import textwrap
import types


K = ctypes.WinDLL('kernel32', use_last_error=True)
K.CreateFileW.argtypes = [W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
K.CreateFileW.restype = W.HANDLE
K.CloseHandle.argtypes = [W.HANDLE]
K.GetFileInformationByHandle.argtypes = [W.HANDLE,ctypes.c_void_p]
class FileInfo(ctypes.Structure):
    _fields_ = [('attributes',W.DWORD),('created',W.FILETIME),('accessed',W.FILETIME),
        ('written',W.FILETIME),('volume',W.DWORD),('size_hi',W.DWORD),('size_lo',W.DWORD),
        ('links',W.DWORD),('index_hi',W.DWORD),('index_lo',W.DWORD)]


class PathPins:
    """Fail-closed path namespace pins, not content immutability."""
    __slots__ = ('handles','identities','active')
    def __init__(self): self.handles=[];self.identities={};self.active=False
    def open(self, paths):
        if self.active: raise ValueError('PIN_ALREADY_ACTIVE')
        files={Path(os.path.abspath(p)) for p in paths}
        dirs={q for p in files for q in p.parents}
        try:
            for p in sorted(dirs,key=lambda p:(len(p.parts),str(p))) + sorted(files):
                h=K.CreateFileW(str(p),0x80000000,1,None,3,0x02000000|0x00200000,None)
                if h == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
                self.handles.append(h);info=FileInfo()
                if not K.GetFileInformationByHandle(h,ctypes.byref(info)): raise ctypes.WinError(ctypes.get_last_error())
                if info.attributes & 1024: raise ValueError('PIN_REPARSE_POINT_REJECTED:'+str(p))
                self.identities[str(p)]=(info.volume,info.index_hi,info.index_lo)
            self.active=True;return self
        except BaseException: self.close();raise
    def close(self):
        self.active=False
        for h in reversed(self.handles): K.CloseHandle(h)
        self.handles.clear()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def __deepcopy__(self,memo):return self


class ReaderLease:
    __slots__=('root','paths','pins','vc','originals','audit','_functions','code_paths')
    def __init__(self, guards, vc):
        self.vc=vc;self.originals=tuple(guards);self.root=guards[0].project_root.resolve()
        self.paths={};self.pins=PathPins();self.audit=[];self._functions={}
        for g in guards:
            if g.project_root.resolve()!=self.root:raise ValueError('MULTIPLE_PROJECT_ROOTS')
            g.verify()
            manifest=vc.read_json(vc.safe_path(self.root,g.manifest_path))
            for rel in [g.manifest_path,manifest['configuration_path']]+[r['path'] for r in manifest['files']+list(manifest['anchors'].values())]:
                self.paths[rel]=vc.safe_path(self.root,rel)
        # The verifier bytecode and this independent adapter are also pinned.
        self.code_paths=(Path(vc.__file__),Path(__file__))
        for p in self.code_paths:
            if p.is_relative_to(self.root):
                self.paths[p.relative_to(self.root).as_posix()]=vc.safe_path(self.root,p.relative_to(self.root).as_posix())
    def __enter__(self):
        self.pins.open([*self.paths.values(),*self.code_paths])
        try:
            # No verification result saved for later use: original guards fully
            # re-check content after acquisition, then every adapted verify hashes
            # the complete dependency bytes again.
            for g in self.originals:g.verify()
            return self
        except BaseException:self.pins.close();raise
    def __exit__(self,*args):self.pins.close()
    def __deepcopy__(self,memo):return self
    def safe_path(self,root,relative):
        if not self.pins.active:raise ValueError('PATH_PIN_LEASE_CLOSED')
        if Path(root)!=self.root or not isinstance(relative,str):raise ValueError('UNPINNED_ROOT_OR_PATH')
        rel=PurePosixPath(relative)
        if rel.is_absolute() or str(rel)!=relative or any(p in ('.','..') or ':' in p for p in rel.parts) or '\\' in relative:
            raise ValueError('NONCANONICAL_PIN_PATH')
        if relative not in self.paths:raise ValueError('UNPINNED_DEPENDENCY:'+relative)
        return self.paths[relative]
    def binding(self,root,rel):return dict(path=rel,**self.vc.file_info(self.safe_path(root,rel)))
    def read_json(self,path):return self.vc.read_json(path)
    def guard(self,g):
        if g not in self.originals:raise ValueError('UNREGISTERED_GUARD')
        cls=type(g)
        if cls not in self._functions:
            old=cls.verify;source=textwrap.dedent(inspect.getsource(old));tree=ast.parse(source)
            reader=self
            class Rewrite(ast.NodeTransformer):
                def visit_FunctionDef(self,node):
                    if node.name=='checked_path':
                        node.body=[ast.Return(ast.Call(ast.Attribute(ast.Name('reader',ast.Load()),'safe_path',ast.Load()),[ast.Name('root',ast.Load()),ast.Name('rel',ast.Load())],[]))]
                        return node
                    return self.generic_visit(node)
                def visit_Assign(self,node):
                    names={x.id for x in node.targets if isinstance(x,ast.Name)}
                    if 'spec' in names:return None
                    if 'vc' in names:return ast.Assign(node.targets,ast.Name('reader',ast.Load()))
                    return self.generic_visit(node)
                def visit_Expr(self,node):
                    if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='exec_module':return None
                    return self.generic_visit(node)
            tree=ast.fix_missing_locations(Rewrite().visit(tree));ns=dict(old.__globals__);ns['reader']=reader
            # vc.file_info is still called for each file, never cached.
            exec(compile(tree,'<N4_P0R_FRESH_HASH_PATH_PIN_ADAPTER>','exec'),ns)
            self._functions[cls]=ns['verify']
            self.audit.append(dict(guard=cls.__name__,original_source=source,adapted_source=ast.unparse(tree),
                changes='Only verifier module lookup and checked path traversal; all raw hash and semantic clauses retained'))
        clone=type(g)(g.project_root,g.manifest_path,g.expected_manifest_sha256)
        object.__setattr__(clone,'verify',VerifyCall(self,self._functions[cls],clone))
        return clone
    def file_info(self,path):
        if not self.pins.active:raise ValueError('PATH_PIN_LEASE_CLOSED')
        return self.vc.file_info(path)


class VerifyCall:
    __slots__=('lease','function','guard')
    def __init__(self,lease,function,guard):self.lease=lease;self.function=function;self.guard=guard
    def __call__(self):
        if not self.lease.pins.active:raise ValueError('PATH_PIN_LEASE_CLOSED')
        return self.function(self.guard)
    def __deepcopy__(self,memo):return self
