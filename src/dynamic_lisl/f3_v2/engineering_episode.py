"""Engineering-only wrapper; reuses the shared Gate D2 episode orchestration."""
from .episode_execution import execute_episode


def run_engineering_episode(engine,validator,schedule,source,proposer,controller,*,
                            output_dir,fixture_id,input_hashes,code_hashes,
                            capacity_tolerance_bit_s):
    if not isinstance(fixture_id,str) or not fixture_id.startswith('ENGINEERING-'):
        raise ValueError('ENGINEERING_FIXTURE_ID_REQUIRED_NOT_REGISTERED_RUN')
    return execute_episode(engine,validator,schedule,source,proposer,controller,
        output_dir=output_dir,fixture_id=fixture_id,input_hashes=input_hashes,code_hashes=code_hashes,
        capacity_tolerance_bit_s=capacity_tolerance_bit_s,engineering_only=True)
