"""Independent candidate binding before cost checks; append only."""
import json
import workflow as w
def main():
    config=w.vc.read_json(w.V/'configs/n4_p0_pilot_semantics_v1.json')
    config.update(schema='dynamic_k_n4_p0r_engineering_v1',stage='N4_P0R',full_epoch_authorized=False,
        optimization=dict(path_namespace_pins=True,fresh_sha256_every_verify=True,positive_validation_cache=False,
            raw_io='WINDOWS_PINNED_HANDLES',pure_geometry_cache=False,additional_workers=0),
        catalog_diagnostic=dict(test_only_wall_limit_s=60.,budget_not_formal_search_limit=True))
    dest=w.V/'configs/n4_p0r_engineering_v1.json'
    with dest.open('x',encoding='utf-8',newline='\n') as f:json.dump(config,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n')
    # Bind final code/tests and exact existing upstream anchors; no self-reference.
    paths=[w.V/'runtime/n4_p0r_reader.py',w.V/'runtime/n4_p0r_handle_reader.py',w.V/'tests/test_n4_p0r_reader.py',
        w.V/'contracts/N4_P0R_EXACT_READER_AND_COST_CN.md',dest]+list(w.A.glob('*.py'))
    paths += [w.V/'runtime/n4_p0.py',w.V/'tests/test_n4_p0.py',w.V/'tools/version_control.py',w.V/'tools/version_control_readme_v1.py']
    def binding(p):return w.vc.binding(w.P,p.relative_to(w.P).as_posix())
    manifest=dict(schema='dynamic_k_n4_p0r_candidate_v1',candidate_revision_id='0011',formal_experiments_authorized=False,
        configuration_path=dest.relative_to(w.P).as_posix(),files=[binding(p) for p in sorted(set(paths))],
        anchors=dict(version_origin=binding(w.V/'version_record.json'),parent_revision=binding(w.V/'revisions/0010/record.json'),
            frozen_p0_manifest=binding(w.V/'acceptance/0010/manifest_final.json')))
    w.write('implementation_manifest.json',manifest);print(json.dumps(binding(w.A/'implementation_manifest.json')),flush=True)
    w.write('pre_implementation_verification.json',dict(status='PASS',scope='N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',
        revision_id='0010',version_record_sha256='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691',
        revision_record_sha256='fa9564caf795279ce608cf7ff31c9a86693c7336238b285a52c95c7ffb66c897',
        verified_file_count=6023,baseline_file_count=5810,excluded_file_count=202,undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        source='actual independent full verify output completed before any 0011 file creation',scientific_gate_pass=False))
if __name__=='__main__':main()
