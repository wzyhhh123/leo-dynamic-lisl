"""Run unchanged historical/protection checks and save actual process evidence."""
import argparse,json,re,subprocess,sys
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['historical','protection']);args=parser.parse_args()
    if args.kind=='historical':
        command=[sys.executable,'-B',str(V/'acceptance/0006/run_historical_regression.py'),str(A/'historical_regression.json')]
        destination=A/'historical_execution_transcript.json'
    else:
        command=[sys.executable,'-B',str(V/'tests/test_version_control.py'),'-v']
        destination=A/'version_protection_tests.json'
    assert not destination.exists()
    completed=subprocess.run(command,cwd=str(P),capture_output=True,text=True,encoding='utf-8',errors='strict')
    result=dict(command=command,exit_code=completed.returncode,stdout=completed.stdout,stderr=completed.stderr,
                scope='ACTUAL_UNCHANGED_TEST_EXECUTION',scientific_gate_pass=False)
    if args.kind=='protection':
        match=re.search(r'Ran (\d+) tests?',completed.stderr)
        result.update(tests_run=int(match.group(1)) if match else None,
                      status='PASS' if completed.returncode==0 and match and int(match.group(1))==22 else 'FAIL')
    with destination.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
    return completed.returncode
if __name__=='__main__':sys.exit(main())
