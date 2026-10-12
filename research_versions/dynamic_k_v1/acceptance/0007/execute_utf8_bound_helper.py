"""Execute an unchanged bound helper as explicitly decoded UTF-8 source."""
import argparse,sys
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path[:0]=[str(V),str(P/'src')]
from runtime.n3_baselines import N3EvidenceBinding

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('helper',choices=('write_report.py','finalize_revision.py'))
    parser.add_argument('--manifest-name',required=True)
    parser.add_argument('--expected-manifest-sha256',required=True)
    parser.add_argument('--helper-arguments',nargs=argparse.REMAINDER,default=[])
    args=parser.parse_args()
    N3EvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0007/'+args.manifest_name,
                      args.expected_manifest_sha256).verify()
    target=A/args.helper
    code=compile(target.read_text(encoding='utf-8'),str(target),'exec')
    sys.argv=[str(target)]+args.helper_arguments
    exec(code,dict(__name__='__main__',__file__=str(target),__builtins__=__builtins__))
if __name__=='__main__':main()
