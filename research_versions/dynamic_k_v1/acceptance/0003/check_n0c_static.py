"""N0c document/schema checks only. No production imports or simulated data."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

from jsonschema import Draft202012Validator

NS = Path(__file__).resolve().parents[2]
PROJECT = NS.parents[1]
CONFIG = NS / "configs/research_v1_DRAFT.json"
CONTRACT = NS / "contracts/research_contract_v1_DRAFT_CN.md"
SCHEMA = NS / "schemas/research_result_v1_DRAFT.schema.json"
TEMPLATE = NS / "schemas/research_result_v1_DRAFT.template.json"
BEFORE = Path(__file__).parent / "before/configuration_before.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    config, before, schema, template = map(read, (CONFIG, BEFORE, SCHEMA, TEMPLATE))
    contract = CONTRACT.read_text(encoding="utf-8")
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append({"name": name, "status": "PASS"})

    Draft202012Validator.check_schema(schema)
    check("draft_2020_12_schema_well_formed", True)
    validator = Draft202012Validator(schema)
    check("unexecuted_template_validates", validator.is_valid(template))
    check("all_seven_scientific_numbers_remain_null", len(config["scientific_parameters"]) == 7
          and all(v is None for v in config["scientific_parameters"].values())
          and template["scientific_parameters"] == config["scientific_parameters"])
    check("all_control_numbers_and_unselected_algorithm_preserved", config["control_parameters"] == before["control_parameters"]
          and all(v is None for v in config["control_parameters"].values())
          and config["algorithm"] == before["algorithm"]
          and template["algorithm_selection"] is None)
    check("no_formal_run_or_production_integration_authorized", config["status"] == "DRAFT_NOT_FROZEN"
          and config["authorized_stage"] == "N0c_STATIC_CONTRACT_SEMANTICS_ONLY"
          and config["formal_experiments_authorized"] is False
          and config["production_runner_integrated"] is False)
    check("unchanged_science_and_original_power_values", all(config[k] == before[k]
          for k in ("scene", "scientific_parameters", "objective_proposal", "delivery_requirement",
                    "experiment_binding_manifests", "out_of_scope", "legacy_240_600_values_inherited",
                    "legacy_K_star_audit_required_before_new_direction"))
          and all(config["power_profile"][k] == v for k, v in before["power_profile"].items()))
    topology = config["topology"]
    check("main_K_requires_real_ACTIVE_new_business_admission", topology["K_definition"] ==
          "cardinality_of_real_ACTIVE_dynamic_connection_instances_admitting_new_business_at_time_t"
          and topology["K_requires_nonempty_traffic"] is False
          and topology["K_counting_unit"] == "ONE_PER_BILATERAL_CONNECTION_INSTANCE_NOT_PER_DIRECTED_ARC_OR_TERMINAL"
          and config["scene"]["extra_artificial_K_max"] is None)
    check("DRAINING_and_SETUP_separate_from_main_K", topology["K_DRAINING_accounting"] ==
          "EXCLUDED_FROM_MAIN_K_COUNT_SEPARATELY"
          and topology["setup_resource_accounting"]["excluded_from_main_K"] is True
          and topology["setup_resource_accounting"]["reservation_and_state_counters_may_overlap"] is True)
    power = config["power_profile"]
    check("actual_initial_state_billed_without_synthetic_setup", power["billing_window"] == "[0,T]"
          and power["initial_state_billing"] == "ACTUAL_EXECUTION_STATE_AND_REMAINING_PHASE_TIME_AT_T0"
          and power["synthetic_initial_connection_action_allowed"] is False
          and power["pre_T0_setup_energy_included"] is False
          and power["missing_timeline_may_be_filled_as_IDLE"] is False)
    check("DRAINING_power_and_duration_mapping_not_double_counted", power["execution_to_energy_state"]["DRAINING"] == "ACTIVE"
          and power["energy_state_ACTIVE_dwell_includes_execution_DRAINING"] is True
          and power["execution_DRAINING_dwell_recorded_separately"] is True)
    check("N1a_and_N1b_are_future_separate_scopes", config["implementation_plan"]["N1a"]["delivered_fluid_age_tracking"] is False
          and config["implementation_plan"]["N1b"]["age_transport_implementation"] is None
          and config["evaluation"]["delivered_fluid_age_implementation_stage"] == "N1b"
          and all(v["implemented"] is False and v["authorized"] is False
                  for v in config["implementation_plan"].values()))
    check("additional_unresolved_numeric_tolerances_are_null", config["evaluation"]["time_comparison_tolerance_s"] is None
          and config["evaluation"]["business_conservation_tolerance_bits"] is None)
    check("schema_and_template_paths_exist", PROJECT / config["result_schema_draft_path"] == SCHEMA
          and PROJECT / config["result_template_draft_path"] == TEMPLATE)
    check("result_template_not_an_experiment", template["record_kind"] == "TEMPLATE_NOT_EXECUTED"
          and all(v is None for v in template["bindings"].values()))
    check("no_fabricated_K_or_energy_or_delivery_measurements", template["topology"]["time_series"] is None
          and all(v is None for v in template["completion"].values())
          and all(v is None for v in template["business_metrics"].values())
          and all(template["energy"][k] is None for k in ("E_LCT_J", "DeltaE_LCT_J", "standby_baseline_energy_J")))
    check("four_energy_and_five_execution_states_reserved", set(template["energy"]["four_energy_state_dwell_s"]) ==
          {"IDLE", "RETARGETING", "ACQUIRING", "ACTIVE"}
          and set(template["energy"]["five_execution_state_dwell_s"]) ==
          {"IDLE", "RETARGETING", "ACQUIRING", "ACTIVE", "DRAINING"}
          and all(v is None for v in template["energy"]["four_energy_state_dwell_s"].values())
          and all(v is None for v in template["energy"]["five_execution_state_dwell_s"].values()))
    check("K_and_SETUP_time_series_fields_reserved", set(schema["$defs"]["topology_sample"]["properties"]) ==
          {"t_s", "K_active_admissible", "K_draining", "setup_connection_count", "setup_terminal_count",
           "retargeting_terminal_count", "acquiring_terminal_count", "setup_reserved_terminal_count"})
    independent = deepcopy(template)
    independent["completion"].update(evaluation_completed_normally=False, all_offered_business_delivered=True)
    check("completion_flags_structurally_independent_first_direction", validator.is_valid(independent))
    independent["completion"].update(evaluation_completed_normally=True, all_offered_business_delivered=False)
    check("completion_flags_structurally_independent_second_direction", validator.is_valid(independent))
    invalid = deepcopy(template)
    invalid["topology"]["DRAINING_in_main_K"] = True
    check("schema_rejects_DRAINING_in_main_K", not validator.is_valid(invalid))
    invalid = deepcopy(template)
    invalid["energy"]["pre_T0_setup_energy_included"] = True
    check("schema_rejects_pre_T0_energy_in_window", not validator.is_valid(invalid))
    invalid = deepcopy(template)
    del invalid["completion"]["all_offered_business_delivered"]
    check("schema_requires_distinct_delivery_completion_field", not validator.is_valid(invalid))
    invalid = deepcopy(template)
    invalid["energy"]["four_energy_state_dwell_s"]["DRAINING"] = None
    check("schema_rejects_fifth_energy_state", not validator.is_valid(invalid))
    invalid = deepcopy(template)
    invalid["energy"]["E_LCT_J"] = "unknown"
    check("schema_rejects_nonnumeric_energy", not validator.is_valid(invalid))
    check("contract_contains_all_requested_scope_boundaries", all(s in contract for s in
          ("主指标 K(t)=|E_dyn_active_admissible(t)|", "SETUP 资源单独记录", "不因初始化而虚构 t=0",
           "t<0", "N1a 仅", "N1b 才", "这些结果字段为 null", "不宣称 N1a、N1b 或任何科学 Gate 通过")))
    assets = []
    for path in (Path(__file__), CONFIG, CONTRACT, SCHEMA, TEMPLATE):
        raw = path.read_bytes()
        assets.append({"path": path.relative_to(PROJECT).as_posix(), "byte_count": len(raw),
                       "sha256": hashlib.sha256(raw).hexdigest()})
    print(json.dumps({"schema": "dynamic_k_n0c_static_validation_report_v1", "status": "PASS",
        "scope": "N0c_DOCUMENT_SEMANTICS_AND_SCHEMA_ONLY", "completed_utc": datetime.now(timezone.utc).isoformat(),
        "checks_count": len(checks), "checks": checks, "checked_assets": assets,
        "jsonschema_version": importlib.metadata.version("jsonschema"),
        "negative_and_boolean_independence_cases": "IN_MEMORY_STRUCTURAL_FIXTURES_NOT_SIMULATED_RESULTS",
        "production_imports": False, "simulations_or_training_executed": False,
        "N1_implemented_or_accepted": False, "scientific_gate_acceptance_claimed": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
