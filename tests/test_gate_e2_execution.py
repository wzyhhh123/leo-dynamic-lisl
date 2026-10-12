"""Gate E2 frozen execution-point and natural-geometry builder tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from dynamic_lisl.gate_e2_experiments import (
    ACQUISITION_S, RETARGET_A_S, RETARGET_B_S, SETUP_S,
    GateE2Assets, physical_execution_key, unique_execution_plan,
)
from dynamic_lisl.gate_e2_parallel import branch_task_plan


PROJECT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((PROJECT/name).read_text(encoding="utf-8-sig"))
def sha(name):return hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


class GateE2ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets=GateE2Assets()
        cls.execution=read("configs/gate_e2_execution_points.json")

    def test_execution_points_are_frozen_exactly_as_authorized(self):
        self.assertEqual(self.execution["rho"],[0.2,0.5,0.8,1.0,1.2])
        self.assertEqual(self.execution["setup_s"],[2.0])
        self.assertEqual(self.execution["routers"],[
            "shortest_propagation","current_state_load_aware"])
        self.assertEqual(self.execution["branches"],[
            "HOLD","IDEAL_SWITCH","REAL_SWITCH"])
        self.assertEqual(self.execution["logical_paired_points"],80)
        self.assertEqual(self.execution["unique_physical_execution_points"],50)
        payload=dict(self.execution);expected=payload.pop("canonical_sha256")
        actual=hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
        self.assertEqual(actual,expected)

    def test_frozen_inputs_match_execution_hash_record(self):
        record=read("configs/gate_e2_execution_points_hashes.json")["files"]
        self.assertEqual({name:sha(name) for name in record},record)

    def test_every_logical_key_matches_the_frozen_physical_key(self):
        for row in self.execution["logical_points"]:
            scenario=self.assets.selected[row["scenario_id"]]
            self.assertEqual(physical_execution_key(
                scenario,row["rho"],row["router"]),
                row["physical_execution_key"])

    def test_duplicate_actions_are_reused_without_changing_logical_records(self):
        plan=unique_execution_plan(self.assets)
        self.assertEqual(len(plan),50)
        sizes=[len(row["logical_points"]) for row in plan]
        self.assertEqual(sizes.count(2),30)
        self.assertEqual(sizes.count(1),20)
        tasks,_=branch_task_plan(self.assets)
        self.assertEqual(len(tasks),120)
        self.assertEqual(sum(row["branch"]=="HOLD" for row in tasks),20)

    def test_setup_and_absolute_traffic_contract(self):
        self.assertEqual(max(RETARGET_A_S,RETARGET_B_S)+ACQUISITION_S,SETUP_S)
        for scenario in self.assets.selected.values():
            trace=self.assets.trace(scenario["t0_s"],0.8)
            self.assertEqual(trace.segments[0].start_s,0.0)
            self.assertEqual(trace.segments[0].end_s,scenario["t0_s"])
            self.assertTrue(all(value==0.0 for value in
                                trace.segments[0].rates_bit_s.values()))
            self.assertEqual(trace.arrival_horizon_s,scenario["t0_s"]+12.0)
            action=self.assets.action(scenario)
            self.assertEqual(action.time_s,scenario["t0_s"])
            self.assertAlmostEqual(action.policy_horizon_s,
                                   scenario["t0_s"]+2.0+1e-7)

    def test_no_eligible_strata_are_preserved_verbatim(self):
        rows=self.execution["no_eligible_strata"]
        self.assertEqual(len(rows),16)
        self.assertEqual(sum(row["status"]=="NO_ELIGIBLE_CASE" for row in rows),8)
        eb=[row for row in rows if row["scenario_class"]==
            "E-B_BBM_CONNECTED_REROUTE"]
        self.assertEqual(len(eb),4)
        self.assertTrue(all(row["status"]=="NO_ELIGIBLE_CASE" for row in eb))

    def test_both_routers_receive_identical_scenario_rho_points(self):
        def key(row):return row["scenario_id"],row["rho"],row["setup_s"]
        primary={key(row) for row in self.execution["logical_points"]
                 if row["router"]=="shortest_propagation"}
        robust={key(row) for row in self.execution["logical_points"]
                if row["router"]=="current_state_load_aware"}
        self.assertEqual(primary,robust)


if __name__=="__main__":unittest.main(verbosity=2)
