from __future__ import annotations

"""
generate_scenario_X720.py

用途
----
1. 启动 STK 并创建一个可复现的理想 Walker-Star 母星座。
2. 默认参数对应当前暂定参考场景：
      18 planes × 40 sats/plane = 720 sats
      altitude = 1200 km
      inclination = 85 deg
      Walker Star
      InterPlanePhaseIncrement = 1
3. 不直接依赖 STK Children 集合顺序作为 plane_id；优先读取 Classical Elements，
   根据 RAAN 聚类轨道面，再按轨内相位排序后命名为 X<plane>_<index>。
4. 输出可审计 manifest、config 和 audit JSON。
5. 该脚本只负责“场景准备/几何母星座”，不负责 traffic、queue、动态 LISL、routing、MPC/RL。

建议
----
- 第一版先用 STK TwoBody + Walker Star 生成理想参考星座。
- 后续网络仿真优先导出 position/velocity，不必强制先拟合成 TLE。
"""

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List

from comtypes.client import CreateObject
from comtypes.gen import STKObjects


DEFAULT_START_TIME = "01 Jan 2026 00:00:00.00"
DEFAULT_STOP_TIME = "02 Jan 2026 00:00:00.00"

DEFAULT_NUM_PLANES = 18
DEFAULT_SATS_PER_PLANE = 40
DEFAULT_ALTITUDE_KM = 1200.0
DEFAULT_INCLINATION_DEG = 85.0
DEFAULT_INTERPLANE_PHASE_INCREMENT = 1

EARTH_RADIUS_KM = 6378.137


def wrap360(x: float) -> float:
    return x % 360.0


def circ_diff_deg(a: float, b: float) -> float:
    """最小圆周角差，范围 [0, 180]."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def circular_mean_deg(values: List[float]) -> float:
    if not values:
        raise ValueError("empty angle list")
    sx = sum(math.cos(math.radians(v)) for v in values)
    sy = sum(math.sin(math.radians(v)) for v in values)
    return wrap360(math.degrees(math.atan2(sy, sx)))


def get_dataset_scalar(result, candidate_names: List[str]) -> float:
    last_error = None
    for name in candidate_names:
        try:
            ds = result.DataSets.GetDataSetByName(name)
            values = ds.GetValues()
            if not values:
                continue
            return float(values[0])
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(
        f"Cannot find any dataset in {candidate_names}; last_error={last_error}"
    )


def read_classical_elements(sat_obj, start_time: str) -> Dict[str, float]:
    """
    从 STK Data Provider 读取初始轨道根数。

    不同 STK 版本 provider 路径可能略有差异，因此尝试 ICRF / J2000。
    对圆轨道，argument of perigee 的物理意义退化；这里用
    argument_of_latitude = arg_perigee + anomaly 作为轨内排序量。
    """
    provider_paths = [
        "Classical Elements/ICRF",
        "Classical Elements/J2000",
    ]
    last_error = None

    for path in provider_paths:
        try:
            dp = sat_obj.DataProviders.GetDataPrvTimeVarFromPath(path)
            result = dp.ExecSingle(start_time)

            sma = get_dataset_scalar(
                result,
                ["Semimajor Axis", "Semi-major Axis", "SemiMajor Axis"],
            )
            ecc = get_dataset_scalar(result, ["Eccentricity"])
            inc = get_dataset_scalar(result, ["Inclination"])
            raan = get_dataset_scalar(
                result,
                ["RAAN", "Right Ascension of Ascending Node"],
            )
            aop = get_dataset_scalar(
                result,
                ["Arg of Perigee", "Argument of Perigee"],
            )

            try:
                anomaly = get_dataset_scalar(
                    result,
                    ["True Anomaly", "TrueAnomaly"],
                )
                anomaly_kind = "true"
            except Exception:  # noqa: BLE001
                anomaly = get_dataset_scalar(
                    result,
                    ["Mean Anomaly", "MeanAnomaly"],
                )
                anomaly_kind = "mean"

            u = wrap360(aop + anomaly)
            return {
                "semi_major_axis_km": sma,
                "eccentricity": ecc,
                "inclination_deg": wrap360(inc),
                "raan_deg": wrap360(raan),
                "arg_perigee_deg": wrap360(aop),
                "anomaly_deg": wrap360(anomaly),
                "anomaly_kind": anomaly_kind,
                "argument_of_latitude_deg": u,
                "provider_path": path,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    raise RuntimeError(
        "Unable to read Classical Elements from STK. "
        f"Tried {provider_paths}. Last error: {last_error}"
    )


def cluster_by_raan(
    sats: List[Dict],
    expected_planes: int,
    sats_per_plane: int,
    tolerance_deg: float,
) -> List[List[Dict]]:
    """根据 RAAN 将卫星聚成轨道面。"""
    sorted_sats = sorted(sats, key=lambda x: x["raan_deg"])
    clusters: List[List[Dict]] = []

    for sat in sorted_sats:
        placed = False
        for cluster in clusters:
            center = circular_mean_deg([x["raan_deg"] for x in cluster])
            if circ_diff_deg(sat["raan_deg"], center) <= tolerance_deg:
                cluster.append(sat)
                placed = True
                break
        if not placed:
            clusters.append([sat])

    clusters.sort(
        key=lambda c: circular_mean_deg([x["raan_deg"] for x in c])
    )

    if len(clusters) != expected_planes:
        raise RuntimeError(
            f"RAAN clustering produced {len(clusters)} planes, "
            f"expected {expected_planes}. Stop."
        )

    bad_sizes = [len(c) for c in clusters if len(c) != sats_per_plane]
    if bad_sizes:
        raise RuntimeError(
            f"Unexpected plane population(s): {bad_sizes}; "
            f"expected exactly {sats_per_plane} satellites per plane."
        )

    return clusters


def assign_plane_and_slot(clusters: List[List[Dict]]) -> List[Dict]:
    """每个 plane 内按 argument of latitude 排序，生成 X<plane>_<sat_id>."""
    assigned: List[Dict] = []
    for plane_id, cluster in enumerate(clusters):
        ordered = sorted(cluster, key=lambda x: x["argument_of_latitude_deg"])
        for idx, sat in enumerate(ordered, start=1):
            sat["plane_id"] = plane_id
            sat["sat_id"] = idx
            sat["final_name"] = f"X{plane_id}_{idx}"
            assigned.append(sat)
    return assigned


def rename_satellites_safely(assigned: List[Dict]) -> None:
    """两阶段重命名，避免旧名/新名碰撞。"""
    for i, sat in enumerate(assigned):
        sat["obj"].InstanceName = f"__TMP_WALKER720_{i:04d}"

    for sat in assigned:
        sat["obj"].InstanceName = sat["final_name"]


def compute_phase_spacing(values: List[float]) -> List[float]:
    vals = sorted(wrap360(v) for v in values)
    diffs = []
    for i in range(len(vals)):
        nxt = vals[(i + 1) % len(vals)]
        cur = vals[i]
        diffs.append((nxt - cur) % 360.0)
    return diffs


def best_interplane_phase_offset(u_a: List[float], u_b: List[float]) -> float:
    """
    两个等规模轨道面之间寻找整体轨内相位偏移。
    sat_id 有循环编号自由度，因此枚举 circular shift。
    """
    a = sorted(wrap360(x) for x in u_a)
    b = sorted(wrap360(x) for x in u_b)
    n = len(a)
    if n != len(b):
        raise ValueError("plane sizes differ")

    best = None
    for shift in range(n):
        offsets = []
        for i in range(n):
            d = ((b[(i + shift) % n] - a[i] + 180.0) % 360.0) - 180.0
            offsets.append(d)
        mean = sum(offsets) / n
        rms = math.sqrt(sum((d - mean) ** 2 for d in offsets) / n)
        if best is None or rms < best[0]:
            best = (rms, mean)

    assert best is not None
    return best[1]


def audit_constellation(
    assigned: List[Dict],
    num_planes: int,
    sats_per_plane: int,
    altitude_km: float,
    inclination_deg: float,
    interplane_phase_increment: int,
    tolerance: Dict[str, float],
) -> Dict:
    """
    做生成后的一致性 Gate。

    注意：这里不硬编码 Walker-Star 必须是 180° RAAN spread；
    而是审计 STK 实际生成的 RAAN 是否形成等间隔平面。
    """
    expected_n = num_planes * sats_per_plane
    expected_intra_spacing = 360.0 / sats_per_plane
    expected_phase_offset = interplane_phase_increment * 360.0 / expected_n

    planes: Dict[int, List[Dict]] = {}
    for sat in assigned:
        planes.setdefault(sat["plane_id"], []).append(sat)

    plane_centers = []
    plane_reports = []
    all_pass = True

    for p in range(num_planes):
        members = planes[p]
        raan_center = circular_mean_deg([x["raan_deg"] for x in members])
        plane_centers.append(raan_center)

        spacings = compute_phase_spacing(
            [x["argument_of_latitude_deg"] for x in members]
        )
        max_spacing_error = max(
            abs(x - expected_intra_spacing) for x in spacings
        )

        inc_err = max(
            abs(x["inclination_deg"] - inclination_deg)
            for x in members
        )

        target_sma = EARTH_RADIUS_KM + altitude_km
        sma_err = max(
            abs(x["semi_major_axis_km"] - target_sma)
            for x in members
        )
        ecc_max = max(abs(x["eccentricity"]) for x in members)

        plane_pass = (
            max_spacing_error <= tolerance["intra_spacing_deg"]
            and inc_err <= tolerance["inclination_deg"]
            and sma_err <= tolerance["semi_major_axis_km"]
            and ecc_max <= tolerance["eccentricity"]
        )
        all_pass = all_pass and plane_pass

        plane_reports.append(
            {
                "plane_id": p,
                "count": len(members),
                "raan_center_deg": raan_center,
                "max_intra_spacing_error_deg": max_spacing_error,
                "max_inclination_error_deg": inc_err,
                "max_semi_major_axis_error_km": sma_err,
                "max_eccentricity": ecc_max,
                "pass": plane_pass,
            }
        )

    raan_diffs = []
    for p in range(num_planes - 1):
        d = (plane_centers[p + 1] - plane_centers[p]) % 360.0
        raan_diffs.append(d)

    if raan_diffs:
        mean_raan_spacing = sum(raan_diffs) / len(raan_diffs)
        max_raan_spacing_deviation = max(
            abs(x - mean_raan_spacing) for x in raan_diffs
        )
    else:
        mean_raan_spacing = 0.0
        max_raan_spacing_deviation = 0.0

    raan_pass = max_raan_spacing_deviation <= tolerance["raan_spacing_deg"]
    all_pass = all_pass and raan_pass

    phase_offsets = []
    phase_errors = []
    for p in range(num_planes - 1):
        u_a = [x["argument_of_latitude_deg"] for x in planes[p]]
        u_b = [x["argument_of_latitude_deg"] for x in planes[p + 1]]
        offset = best_interplane_phase_offset(u_a, u_b)

        # 轨内编号有 9°循环自由度，所以把 offset 约化到一个轨内间隔附近。
        spacing = expected_intra_spacing
        reduced = ((offset + spacing / 2.0) % spacing) - spacing / 2.0

        # 只审计偏移量绝对值是否接近期望；相位方向由 STK Walker 命名约定决定。
        err = min(
            abs(reduced - expected_phase_offset),
            abs(reduced + expected_phase_offset),
        )
        phase_offsets.append(reduced)
        phase_errors.append(err)

    max_phase_error = max(phase_errors) if phase_errors else 0.0
    phase_pass = max_phase_error <= tolerance["interplane_phase_deg"]
    all_pass = all_pass and phase_pass

    names = [x["final_name"] for x in assigned]
    name_unique = len(names) == len(set(names)) == expected_n
    all_pass = all_pass and name_unique

    return {
        "pass": all_pass,
        "expected": {
            "total_satellites": expected_n,
            "num_planes": num_planes,
            "sats_per_plane": sats_per_plane,
            "altitude_km": altitude_km,
            "inclination_deg": inclination_deg,
            "interplane_phase_increment": interplane_phase_increment,
            "expected_intra_spacing_deg": expected_intra_spacing,
            "expected_adjacent_plane_phase_offset_deg": expected_phase_offset,
        },
        "observed": {
            "total_satellites": len(assigned),
            "unique_names": name_unique,
            "plane_raan_centers_deg": plane_centers,
            "adjacent_raan_spacings_deg": raan_diffs,
            "mean_adjacent_raan_spacing_deg": mean_raan_spacing,
            "max_adjacent_raan_spacing_deviation_deg": max_raan_spacing_deviation,
            "adjacent_plane_phase_offsets_reduced_deg": phase_offsets,
            "max_adjacent_plane_phase_error_deg": max_phase_error,
        },
        "plane_reports": plane_reports,
        "tolerances": tolerance,
    }


def write_manifest(path: Path, assigned: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sat_name",
        "plane_id",
        "sat_id",
        "semi_major_axis_km",
        "eccentricity",
        "inclination_deg",
        "raan_deg",
        "arg_perigee_deg",
        "anomaly_deg",
        "anomaly_kind",
        "argument_of_latitude_deg",
        "provider_path",
    ]

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for sat in sorted(assigned, key=lambda x: (x["plane_id"], x["sat_id"])):
            writer.writerow(
                {
                    "sat_name": sat["final_name"],
                    "plane_id": sat["plane_id"],
                    "sat_id": sat["sat_id"],
                    "semi_major_axis_km": f'{sat["semi_major_axis_km"]:.9f}',
                    "eccentricity": f'{sat["eccentricity"]:.12g}',
                    "inclination_deg": f'{sat["inclination_deg"]:.9f}',
                    "raan_deg": f'{sat["raan_deg"]:.9f}',
                    "arg_perigee_deg": f'{sat["arg_perigee_deg"]:.9f}',
                    "anomaly_deg": f'{sat["anomaly_deg"]:.9f}',
                    "anomaly_kind": sat["anomaly_kind"],
                    "argument_of_latitude_deg": f'{sat["argument_of_latitude_deg"]:.9f}',
                    "provider_path": sat["provider_path"],
                }
            )


def create_walker_constellation(
    scenario_name: str,
    constellation_name: str,
    num_planes: int,
    sats_per_plane: int,
    altitude_km: float,
    inclination_deg: float,
    interplane_phase_increment: int,
    start_time: str,
    stop_time: str,
    output_dir: Path,
    save_scenario: str | None,
    stk_progid: str,
) -> None:
    print("Launching STK...")
    stk_app = CreateObject(stk_progid)
    stk_app.Visible = True
    stk_app.UserControl = True
    root = stk_app.Personality2

    print(f"Preparing scenario: {scenario_name}")
    try:
        root.NewScenario(scenario_name)
    except Exception:
        pass

    scenario = root.CurrentScenario
    if scenario is None:
        raise RuntimeError("STK has no current scenario.")

    if scenario.InstanceName != scenario_name:
        raise RuntimeError(
            f"Current STK scenario is '{scenario.InstanceName}', "
            f"but requested '{scenario_name}'. "
            "Please close the old scenario or change --scenario-name."
        )

    scenario2 = scenario.QueryInterface(STKObjects.IAgScenario)
    scenario2.StartTime = start_time
    scenario2.StopTime = stop_time
    root.Rewind()

    if scenario.Children.Contains(STKObjects.eSatellite, constellation_name):
        scenario.Children.Item(constellation_name).Unload()

    print(
        "Creating Walker Star base satellite: "
        f"{num_planes} planes x {sats_per_plane} sats/plane, "
        f"h={altitude_km} km, i={inclination_deg} deg, "
        f"F={interplane_phase_increment}"
    )

    base_sat = scenario.Children.New(STKObjects.eSatellite, constellation_name)
    satellite = base_sat.QueryInterface(STKObjects.IAgSatellite)
    propagator = satellite.Propagator.QueryInterface(
        STKObjects.IAgVePropagatorTwoBody
    )

    # 沿用旧 X100 脚本的坐标枚举值 3。
    propagator.InitialState.Representation.AssignClassical(
        3,
        EARTH_RADIUS_KM + altitude_km,
        0.0,
        inclination_deg,
        0.0,
        0.0,
        0.0,
    )
    propagator.Propagate()

    walker_cmd = (
        f"Walker */Satellite/{constellation_name} "
        "Type Star "
        f"NumPlanes {num_planes} "
        f"NumSatsPerPlane {sats_per_plane} "
        f"InterPlanePhaseIncrement {interplane_phase_increment} "
        "ColorByPlane Yes"
    )
    print(f"Executing STK command:\n  {walker_cmd}")
    root.ExecuteCommand(walker_cmd)

    base_sat.Unload()

    sat_collection = scenario.Children.GetElements(STKObjects.eSatellite)
    expected_count = num_planes * sats_per_plane
    actual_count = sat_collection.Count

    if actual_count != expected_count:
        raise RuntimeError(
            f"STK created {actual_count} satellites, expected exactly "
            f"{expected_count}. Stop."
        )

    print("Reading initial classical elements for all satellites...")
    sats: List[Dict] = []
    for idx in range(actual_count):
        sat_item = sat_collection.Item(idx)
        elems = read_classical_elements(sat_item, start_time)
        sats.append(
            {
                "obj": sat_item,
                "original_name": sat_item.InstanceName,
                **elems,
            }
        )

    print("Inferring orbital planes from RAAN...")
    clusters = cluster_by_raan(
        sats,
        expected_planes=num_planes,
        sats_per_plane=sats_per_plane,
        tolerance_deg=0.05,
    )

    assigned = assign_plane_and_slot(clusters)

    print("Renaming satellites to X<plane>_<index> ...")
    rename_satellites_safely(assigned)

    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "constellation_manifest_720.csv"
    audit_path = output_dir / "constellation_audit_720.json"
    config_path = output_dir / "constellation_config_720.json"

    write_manifest(manifest_path, assigned)

    tolerance = {
        "semi_major_axis_km": 1e-3,
        "eccentricity": 1e-9,
        "inclination_deg": 1e-6,
        "intra_spacing_deg": 1e-4,
        "raan_spacing_deg": 1e-4,
        "interplane_phase_deg": 1e-3,
    }

    audit = audit_constellation(
        assigned=assigned,
        num_planes=num_planes,
        sats_per_plane=sats_per_plane,
        altitude_km=altitude_km,
        inclination_deg=inclination_deg,
        interplane_phase_increment=interplane_phase_increment,
        tolerance=tolerance,
    )

    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    config = {
        "generator": "generate_scenario_X720.py",
        "scenario_name": scenario_name,
        "constellation_name_seed": constellation_name,
        "walker_type": "Star",
        "num_planes": num_planes,
        "sats_per_plane": sats_per_plane,
        "total_satellites": expected_count,
        "altitude_km": altitude_km,
        "inclination_deg": inclination_deg,
        "interplane_phase_increment": interplane_phase_increment,
        "start_time": start_time,
        "stop_time": stop_time,
        "propagator": "TwoBody",
        "earth_radius_km_used_for_seed": EARTH_RADIUS_KM,
        "naming": "X<plane>_<sat_id>, plane 0-based, sat_id 1-based",
        "notes": [
            "Idealized literature-style Walker-Star reference constellation.",
            "Do not call this a current real OneWeb TLE constellation.",
            "Plane IDs are inferred from RAAN; in-plane IDs are inferred from argument of latitude.",
            "Network-layer dynamic LISL, traffic, queue, setup, routing and RL/MPC are intentionally not created here.",
        ],
    }
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    if save_scenario:
        print(f"Saving STK scenario to: {save_scenario}")
        root.SaveAs(save_scenario)

    print()
    print("=" * 72)
    print(f"Walker-Star mother constellation created: {expected_count} satellites")
    print(f"Manifest: {manifest_path}")
    print(f"Audit:    {audit_path}")
    print(f"Config:   {config_path}")
    print(f"AUDIT RESULT: {'PASS' if audit['pass'] else 'FAIL'}")
    print("=" * 72)

    if not audit["pass"]:
        raise RuntimeError(
            "Constellation audit FAILED. "
            "Do not export TLE/ephemeris or start network experiments."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and audit a 720-satellite Walker-Star mother constellation in STK."
    )
    parser.add_argument(
        "--scenario-name",
        default="WalkerStar_720_1200km_85deg",
    )
    parser.add_argument(
        "--constellation-name",
        default="Walker720_Base",
    )
    parser.add_argument("--num-planes", type=int, default=DEFAULT_NUM_PLANES)
    parser.add_argument(
        "--sats-per-plane", type=int, default=DEFAULT_SATS_PER_PLANE
    )
    parser.add_argument("--altitude-km", type=float, default=DEFAULT_ALTITUDE_KM)
    parser.add_argument(
        "--inclination-deg", type=float, default=DEFAULT_INCLINATION_DEG
    )
    parser.add_argument(
        "--interplane-phase-increment",
        type=int,
        default=DEFAULT_INTERPLANE_PHASE_INCREMENT,
    )
    parser.add_argument("--start-time", default=DEFAULT_START_TIME)
    parser.add_argument("--stop-time", default=DEFAULT_STOP_TIME)
    parser.add_argument(
        "--output-dir",
        default="./walker720_artifacts",
        help="Directory for manifest/audit/config outputs.",
    )
    parser.add_argument(
        "--save-scenario",
        default=None,
        help="Optional .sc path for STK SaveAs.",
    )
    parser.add_argument(
        "--stk-progid",
        default="STK11.Application",
        help="e.g. STK11.Application",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    create_walker_constellation(
        scenario_name=args.scenario_name,
        constellation_name=args.constellation_name,
        num_planes=args.num_planes,
        sats_per_plane=args.sats_per_plane,
        altitude_km=args.altitude_km,
        inclination_deg=args.inclination_deg,
        interplane_phase_increment=args.interplane_phase_increment,
        start_time=args.start_time,
        stop_time=args.stop_time,
        output_dir=Path(args.output_dir),
        save_scenario=args.save_scenario,
        stk_progid=args.stk_progid,
    )
