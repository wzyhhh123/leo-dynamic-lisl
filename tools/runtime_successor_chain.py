"""Read-only exact successor verification for production preflight bookkeeping."""
from pathlib import Path
from dynamic_lisl.b4_runtime_seal import canonical, read, sha, executor_compatibility_successor

EXECUTOR='src/dynamic_lisl/gate_f3_p1_execution.py'
REGISTRY='configs/b4_executor_compatibility_successor_v1.json'
REGISTRY_SHA='e3ea7f5ef62ecbd3d329dbc66095abfad14a5f3042de84a094df4f89076eeec9'

def validate_runtime_chain(root, file, historical_tail_hash, current_hash,
                           authorized_successor_registry=None):
    """Walk explicit, hash-pinned registry entries; no discovery or fuzzy matching."""
    chain=[historical_tail_hash]
    def fail(reason):
        return {'pass':False,'reason':reason,'file':file,'validated_chain':chain}
    if current_hash==historical_tail_hash:
        return {'pass':True,'reason':'HISTORICAL_TAIL','file':file,'validated_chain':chain}
    production=authorized_successor_registry is None
    entries=authorized_successor_registry
    if production:
        entries=([{'path':REGISTRY,'sha256':REGISTRY_SHA}] if file==EXECUTOR else [])
    if not entries:
        return fail('UNREGISTERED_SUCCESSOR')
    cursor=historical_tail_hash
    try:
        for entry in entries:
            path=(root/entry['path']).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                return fail('UNREGISTERED_SUCCESSOR')
            if sha(path)!=entry['sha256']:
                return fail('REGISTRY_HASH_MISMATCH')
            registry=read(path)
            if canonical(registry)!=registry.get('canonical_sha256'):
                return fail('REGISTRY_HASH_MISMATCH')
            if registry.get('file')!=file:
                return fail('UNREGISTERED_SUCCESSOR')
            if registry.get('status') not in ('PASS','AUTHORIZED','AUTHORIZED_RUNTIME_SUCCESSOR') or not registry.get('authorization_gate'):
                return fail('GATE_NOT_PASS')
            if registry.get('parent_hash')!=cursor:
                return fail('PARENT_HASH_MISMATCH')
            successor=registry.get('successor_hash')
            if not successor or successor in chain:
                return fail('BROKEN_SUCCESSOR_CHAIN')
            evidence=registry.get('evidence',{})
            evidence_path=(root/evidence.get('report','')).resolve()
            if not evidence_path.is_relative_to(root.resolve()) or not evidence_path.is_file():
                return fail('MISSING_GATE_EVIDENCE')
            if sha(evidence_path)!=evidence.get('report_sha256'):
                return fail('REGISTRY_HASH_MISMATCH')
            doc=read(evidence_path)
            if doc.get('status') not in ('PASS','CANDIDATE_SUCCESSOR_VALIDATED') or doc.get('scientific_semantics_unchanged') is not True:
                return fail('GATE_NOT_PASS')
            if doc.get('file')!=file or doc.get('H_old')!=cursor or doc.get('H_new')!=successor:
                return fail('BROKEN_SUCCESSOR_CHAIN')
            multi_path=(root/doc.get('multi_epoch_report','')).resolve()
            if not multi_path.is_relative_to(root.resolve()) or not multi_path.is_file():
                return fail('MISSING_GATE_EVIDENCE')
            support=doc.get('supporting_evidence',[])
            if not any((root/x['report']).resolve()==multi_path for x in support):
                return fail('MISSING_GATE_EVIDENCE')
            for item in support:
                p=(root/item['report']).resolve()
                if not p.is_relative_to(root.resolve()) or not p.is_file():
                    return fail('MISSING_GATE_EVIDENCE')
                if sha(p)!=item['report_sha256']:
                    return fail('REGISTRY_HASH_MISMATCH')
            multi=read(multi_path)
            if multi.get('status')!='MULTI_EPOCH_EXACT_EQUIVALENCE_PASS' or multi.get('all_epoch_branch_and_state_exact') is not True:
                return fail('GATE_NOT_PASS')
            if production and not executor_compatibility_successor(root,cursor,successor):
                return fail('BROKEN_SUCCESSOR_CHAIN')
            cursor=successor;chain.append(cursor)
        if cursor!=current_hash or sha(root/file)!=current_hash:
            return fail('CURRENT_HASH_MISMATCH')
        return {'pass':True,'reason':'AUTHORIZED_SUCCESSOR_CHAIN','file':file,
                'validated_chain':chain,'registry_entries':entries}
    except (KeyError,OSError,ValueError,TypeError):
        return fail('BROKEN_SUCCESSOR_CHAIN')
