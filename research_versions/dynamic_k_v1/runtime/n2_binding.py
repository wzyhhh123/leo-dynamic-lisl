"""Pinned N2 candidate guard; old N1a/N1b guards remain authoritative."""
import importlib.util
from pathlib import Path
from .bindings import EngineeringBinding
from .n1a import require


class N2EvidenceBinding(EngineeringBinding):
    def verify(self):
        spec=importlib.util.spec_from_file_location('n2_binding_vc',Path(__file__).resolve().parents[1]/'tools/version_control.py')
        vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
        root=self.project_root
        info=vc.file_info(vc.safe_path(root,self.manifest_path))
        require(info['sha256']==self.expected_manifest_sha256,'N2_CANDIDATE_ANCHOR_MISMATCH')
        m=vc.read_json(vc.safe_path(root,self.manifest_path))
        require(m['schema']=='dynamic_k_n2_candidate_v1' and m['candidate_revision_id']=='0006'
                and m['formal_experiments_authorized'] is False,'N2_UNAUTHORIZED_BINDING')
        seen=set()
        for row in m['files']+list(m['anchors'].values()):
            require(row['path'] not in seen,'DUPLICATE_N2_BINDING');seen.add(row['path'])
            require(vc.file_info(vc.safe_path(root,row['path']))=={k:row[k] for k in ('byte_count','sha256')},
                    'N2_FILE_BINDING_MISMATCH:'+row['path'])
        c=vc.read_json(vc.safe_path(root,m['configuration_path']))
        require(all(v is None for v in c['scientific_parameters'].values())
                and all(c[k] is None for k in ('fixed_K','Kmax','decision_period_s','maximum_concurrent_actions',
                    'search_budget','algorithm_selection','minimum_delivery_rate_hard_mask','connectivity_rejection_policy'))
                and c['partition_allowed'] is True and c['formal_experiments_authorized'] is False,
                'N2_UNAUTHORIZED_SCIENTIFIC_FREEZE_OR_MASK')
        return dict(scope='ENGINEERING_TEST_ONLY',candidate_revision_id='0006',
                    implementation_manifest=dict(path=self.manifest_path,**info),anchors=m['anchors'])
