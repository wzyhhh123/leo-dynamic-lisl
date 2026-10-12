"""Pinned candidate implementation bindings for engineering tests, not formal runs."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .n1a import require


@dataclass(frozen=True)
class EngineeringBinding:
    project_root: Path
    manifest_path: str
    expected_manifest_sha256: str

    def verify(self):
        root = self.project_root.resolve()

        def checked_path(rel):
            require(isinstance(rel, str) and '\\' not in rel and ':' not in rel,
                    'NONCANONICAL_BINDING_PATH')
            p = root / rel
            require(not Path(rel).is_absolute() and '..' not in Path(rel).parts
                    and p.resolve().is_relative_to(root), 'BINDING_OUTSIDE_PROJECT')
            require(not any(q.is_symlink() for q in (p, *p.parents) if q != root.parent),
                    'SYMLINK_BINDING_REJECTED')
            return p

        def raw_info(path):
            before = path.stat()
            content = path.read_bytes()
            after = path.stat()
            require(before.st_size == after.st_size == len(content)
                    and before.st_mtime_ns == after.st_mtime_ns, 'BINDING_CHANGED_DURING_READ')
            return dict(byte_count=len(content), sha256=hashlib.sha256(content).hexdigest())

        p = checked_path(self.manifest_path)
        info = raw_info(p)
        require(info['sha256'] == self.expected_manifest_sha256,
                'ENGINEERING_MANIFEST_ANCHOR_MISMATCH')
        manifest = json.loads(p.read_text(encoding='utf-8'))
        require(manifest['schema'] == 'dynamic_k_n1a_candidate_implementation_v1'
                and manifest['scope'] == 'ENGINEERING_TEST_ONLY'
                and manifest['candidate_revision_id'] == '0004'
                and manifest['formal_experiments_authorized'] is False,
                'UNAUTHORIZED_ENGINEERING_BINDING')
        rows = manifest['files'] + list(manifest['anchors'].values())
        seen = set()
        for row in rows:
            require(row['path'] not in seen, 'DUPLICATE_ENGINEERING_BINDING')
            seen.add(row['path'])
            require(raw_info(checked_path(row['path'])) ==
                    {k: row[k] for k in ('byte_count', 'sha256')},
                    'ENGINEERING_FILE_BINDING_MISMATCH:' + row['path'])
        configuration = json.loads(checked_path(manifest['configuration_path']).read_text(encoding='utf-8'))
        require(configuration['formal_experiments_authorized'] is False
                and all(value is None for value in configuration['scientific_parameters'].values())
                and configuration['algorithm']['selection'] is None,
                'SCIENCE_FREEZE_OR_FORMAL_RUN_OUT_OF_SCOPE')
        return dict(candidate_revision_id='0004', scope='ENGINEERING_TEST_ONLY',
                    implementation_manifest=dict(path=self.manifest_path, **info),
                    version_origin=manifest['anchors']['version_origin'],
                    parent_revision=manifest['anchors']['parent_revision'],
                    baseline_seal=manifest['anchors']['baseline_seal'])
