"""Fresh verification, Windows pins and hostile mapping checks on test copies."""
import ctypes,hashlib,json,mmap,os,subprocess,tempfile,unittest
from pathlib import Path
from runtime.bindings import EngineeringBinding
from runtime.n4_p0r_reader import PathPins,K
from runtime.n4_p0r_handle_reader import HandleReaderLease as ReaderLease
VC=None
AUDIT=[]

class ReaderTests(unittest.TestCase):
    def case(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        (root/'leaf').write_bytes(b'original bytes\r\n')
        (root/'config.json').write_text(json.dumps(dict(formal_experiments_authorized=False,
            scientific_parameters=dict(T=None),algorithm=dict(selection=None))))
        row=lambda rel:dict(path=rel,**VC.file_info(root/rel))
        doc=dict(schema='dynamic_k_n1a_candidate_implementation_v1',scope='ENGINEERING_TEST_ONLY',candidate_revision_id='0004',
            formal_experiments_authorized=False,configuration_path='config.json',files=[row('leaf'),row('config.json')],
            anchors={k:row('leaf') for k in ('version_origin','parent_revision','baseline_seal')})
        # Frozen guards forbid duplicate anchor paths, so give each anchor its own
        # independent byte-identical file. No historical asset touched.
        for k in doc['anchors']:(root/k).write_bytes(b'anchor');doc['anchors'][k]=row(k)
        (root/'manifest.json').write_text(json.dumps(doc));guard=EngineeringBinding(root,'manifest.json',VC.file_info(root/'manifest.json')['sha256'])
        return root,guard
    def test_01_original_descriptor_and_clone_equal(self):
        from copy import deepcopy
        root,g=self.case();expected=g.verify()
        with ReaderLease([g],VC) as r:
            h=r.guard(g);self.assertIs(type(h),type(g));self.assertEqual(expected,h.verify());self.assertEqual(expected,deepcopy(h).verify())
        with self.assertRaisesRegex(ValueError,'LEASE_CLOSED'):h.verify()
        self.assertEqual(expected,g.verify())
    def test_02_writes_deletes_replace_and_ancestor_rename_rejected(self):
        root,g=self.case()
        with ReaderLease([g],VC) as r:
            h=r.guard(g);results={}
            for name,operation in [('write',lambda:(root/'leaf').write_bytes(b'tamper')),('delete',lambda:(root/'leaf').unlink()),
                ('rename',lambda:(root/'leaf').rename(root/'renamed')),('ancestor_rename',lambda:root.rename(root.with_name(root.name+'_renamed')))]:
                with self.assertRaises(OSError):operation()
                results[name]='OS_REJECTED'
            (root/'new').write_bytes(b'new')
            with self.assertRaises(OSError):os.replace(root/'new',root/'leaf')
            results['replace']='OS_REJECTED';self.assertEqual(h.verify(),g.verify());AUDIT.append(results)
    def test_03_preexisting_writer_fails_closed(self):
        root,g=self.case()
        with (root/'leaf').open('r+b') as stream:
            with self.assertRaises(OSError):
                with ReaderLease([g],VC):pass
        AUDIT.append(dict(preexisting_writer='PIN_ACQUISITION_REJECTED'))
    def test_04_tamper_after_close_rejected_new_lease(self):
        root,g=self.case()
        with ReaderLease([g],VC) as r:self.assertEqual(r.guard(g).verify(),g.verify())
        (root/'leaf').write_bytes(b'altered\n')
        with self.assertRaisesRegex(ValueError,'FILE_BINDING_MISMATCH'):
            with ReaderLease([g],VC):pass
    def test_05_unpinned_paths_and_roots_rejected(self):
        root,g=self.case()
        with ReaderLease([g],VC) as r:
            for rel in ('../leaf','./leaf','leaf\\x','unknown','D:/leaf'):
                with self.assertRaises(ValueError):r.safe_path(root,rel)
            with self.assertRaises(ValueError):r.safe_path(root.parent,'leaf')
    def test_06_reparse_input_rejected(self):
        root,g=self.case();target=root/'target';target.mkdir();junction=root/'junction'
        cmd=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(target)],capture_output=True,text=True)
        self.assertEqual(cmd.returncode,0,cmd.stdout+cmd.stderr)
        with self.assertRaisesRegex(ValueError,'REPARSE_POINT'):
            PathPins().open([junction/'file'])
        junction.rmdir()
    def test_07_preexisting_native_writable_mapping_not_trusted(self):
        root,g=self.case();p=root/'leaf'
        K.CreateFileMappingW.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_wchar_p]
        K.CreateFileMappingW.restype=ctypes.c_void_p
        K.MapViewOfFile.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_size_t];K.MapViewOfFile.restype=ctypes.c_void_p
        K.UnmapViewOfFile.argtypes=[ctypes.c_void_p]
        h=K.CreateFileW(str(p),0xC0000000,7,None,3,0,None);self.assertNotEqual(h,ctypes.c_void_p(-1).value)
        section=K.CreateFileMappingW(h,None,4,0,0,None);K.CloseHandle(h);self.assertTrue(section)
        view=K.MapViewOfFile(section,2,0,0,0);self.assertTrue(view)
        try:
            lease=ReaderLease([g],VC)
            try:lease.__enter__()
            except OSError:
                AUDIT.append(dict(native_writable_mapping='PIN_ACQUISITION_REJECTED'));return
            try:
                ctypes.memmove(view,b'X',1)
                self.assertEqual(p.read_bytes()[:1],b'X')
                with self.assertRaisesRegex(ValueError,'FILE_BINDING_MISMATCH'):lease.guard(g).verify()
                AUDIT.append(dict(native_writable_mapping='MUTATION_POSSIBLE_DESPITE_SHARE_DENY_WRITE',
                    fresh_raw_hash='TAMPER_REJECTED',positive_validation_cache='FORBIDDEN'))
            finally:lease.__exit__(None,None,None)
        finally:K.UnmapViewOfFile(view);K.CloseHandle(section)
    def test_08_raw_binary_empty_multiblock_hash_exact_and_never_cached(self):
        root,g=self.case()
        values=[b'',bytes(range(256)),b'\r\n\x00\n'+bytes(range(256))*32769]
        for data in values:
            (root/'leaf').write_bytes(data)
            doc=json.loads((root/'manifest.json').read_text());doc['files'][0]=dict(path='leaf',**VC.file_info(root/'leaf'))
            (root/'manifest.json').write_text(json.dumps(doc));h=EngineeringBinding(root,'manifest.json',VC.file_info(root/'manifest.json')['sha256'])
            with ReaderLease([h],VC) as lease:
                start=lease.reads;expected=VC.file_info(root/'leaf')
                self.assertEqual(lease.file_info(root/'leaf'),expected);self.assertEqual(lease.file_info(root/'leaf'),expected)
                self.assertEqual(lease.reads-start,2);self.assertEqual(lease.guard(h).verify(),h.verify())

if __name__=='__main__':unittest.main()
