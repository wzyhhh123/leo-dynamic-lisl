"""Fresh SHA-256 from pinned Windows handles; no validated-content cache.

Original guard clauses, raw byte counts and descriptors are preserved. Windows
handle metadata is compared before/after every complete raw read. Path identity
is pinned by the inherited fail-closed non-reparse ancestor/file share locks.
Single-process read pointer access is serialized even for cloned guard objects.
"""
import ast,ctypes,hashlib,inspect,os,textwrap,threading
from ctypes import wintypes as W
from pathlib import Path
from .n4_p0r_reader import ReaderLease,PathPins,FileInfo,K,VerifyCall

K.SetFilePointerEx.argtypes=[W.HANDLE,ctypes.c_longlong,ctypes.POINTER(ctypes.c_longlong),W.DWORD]
K.ReadFile.argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.c_void_p]

class HandlePins(PathPins):
    __slots__=('by_path',)
    def __init__(self):super().__init__();self.by_path={}
    def open(self,paths):
        files={Path(os.path.abspath(p)) for p in paths};dirs={q for p in files for q in p.parents}
        ordered=sorted(dirs,key=lambda p:(len(p.parts),str(p)))+sorted(files)
        super().open(paths);self.by_path=dict(zip(ordered,self.handles));return self
    def close(self):super().close();self.by_path.clear()

class HandleReaderLease(ReaderLease):
    __slots__=('lock','_handle_functions','reads','bytes_hashed')
    def __init__(self,guards,vc):
        super().__init__(guards,vc);self.pins=HandlePins();self.lock=threading.RLock()
        self._handle_functions={};self.reads=0;self.bytes_hashed=0
        self.code_paths=(*self.code_paths,Path(__file__))
    def _read_verified(self,path,n1a=False):
        if not self.pins.active:raise ValueError('PATH_PIN_LEASE_CLOSED')
        path=Path(path)
        if path not in self.pins.by_path:raise ValueError('UNPINNED_RAW_READ')
        with self.lock:
            h=self.pins.by_path[path];before=FileInfo();after=FileInfo()
            if not K.GetFileInformationByHandle(h,ctypes.byref(before)):raise ctypes.WinError(ctypes.get_last_error())
            if (before.volume,before.index_hi,before.index_lo)!=self.pins.identities[str(path)]:raise ValueError('PIN_IDENTITY_CHANGED')
            size=(before.size_hi<<32)|before.size_lo
            if not K.SetFilePointerEx(h,0,None,0):raise ctypes.WinError(ctypes.get_last_error())
            buffer=ctypes.create_string_buffer(min(8*1024*1024,max(1,size)));n=W.DWORD();digest=hashlib.sha256();total=0
            while True:
                if not K.ReadFile(h,buffer,len(buffer),ctypes.byref(n),None):raise ctypes.WinError(ctypes.get_last_error())
                if not n.value:break
                digest.update(memoryview(buffer).cast('B')[:n.value]);total+=n.value
            if not K.GetFileInformationByHandle(h,ctypes.byref(after)):raise ctypes.WinError(ctypes.get_last_error())
            stable=(before.size_hi,before.size_lo,before.written.dwHighDateTime,before.written.dwLowDateTime)==(after.size_hi,after.size_lo,after.written.dwHighDateTime,after.written.dwLowDateTime)
            if not stable or total!=size:
                if n1a:raise ValueError('BINDING_CHANGED_DURING_READ')
                self.vc.require(False,'FILE_CHANGED_WHILE_READING',str(path))
            self.reads+=1;self.bytes_hashed+=total
            return dict(byte_count=total,sha256=digest.hexdigest())
    def file_info(self,path):return self._read_verified(path)
    def raw_info(self,path):return self._read_verified(path,True)
    def binding(self,root,rel):return dict(path=rel,**self.file_info(self.safe_path(root,rel)))
    def guard(self,g):
        h=super().guard(g);cls=type(g)
        if cls not in self._handle_functions:
            # For N1a only, replace its local raw_info implementation with the
            # fresh handle reader. N1b/N2/N3/P0 already call reader.file_info.
            source=next(a['adapted_source'] for a in self.audit if a['guard']==cls.__name__)
            tree=ast.parse(source)
            class Raw(ast.NodeTransformer):
                def visit_FunctionDef(self,node):
                    if node.name=='raw_info':
                        node.body=[ast.Return(ast.Call(ast.Attribute(ast.Name('reader',ast.Load()),'raw_info',ast.Load()),[ast.Name('path',ast.Load())],[]))];return node
                    return self.generic_visit(node)
            tree=ast.fix_missing_locations(Raw().visit(tree));ns=dict(cls.verify.__globals__);ns['reader']=self
            exec(compile(tree,'<N4_P0R_FRESH_HANDLE_SHA_ADAPTER>','exec'),ns);self._handle_functions[cls]=ns['verify']
            self.audit.append(dict(guard=cls.__name__+'_FRESH_HANDLE',original_source=inspect.getsource(cls.verify),
                adapted_source=ast.unparse(tree),changes='Raw I/O uses pinned handle, before/after metadata and complete fresh SHA-256; semantic clauses unchanged'))
        object.__setattr__(h,'verify',VerifyCall(self,self._handle_functions[cls],h));return h
