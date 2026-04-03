#!/usr/bin/env python3
"""Extract BEPS, LV-B, LV-D, LV-I, LS-A, LV-M, ES-D, and PS-H report data from an eQuest .SIM file."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List
END_USE_COLUMNS = [
    "LIGHTS",
    "TASK LIGHTS",
    "MISC EQUIP",
    "SPACE HEATING",
    "SPACE COOLING",
    "HEAT REJECT",
    "PUMPS & AUX",
    "VENT FANS",
    "REFRIG DISPLAY",
    "HT PUMP SUPPLEM",
    "DOMEST HOT WTR",
    "EXT USAGE",
    "TOTAL",
]
LV_D_COLUMNS = [
    "orientation",
    "avg_u_value_windows",
    "avg_u_value_walls",
    "avg_u_value_walls_plus_windows",
    "window_area",
    "wall_area",
    "window_plus_wall_area",
]
LV_D_UNITS = {
    "avg_u_value_windows": "BTU/HR-SQFT-F",
    "avg_u_value_walls": "BTU/HR-SQFT-F",
    "avg_u_value_walls_plus_windows": "BTU/HR-SQFT-F",
    "window_area": "SQFT",
    "wall_area": "SQFT",
    "window_plus_wall_area": "SQFT",
}
LV_D_TARGET_ORIENTATIONS = {
    "NORTH",
    "NORTH-EAST",
    "EAST",
    "SOUTH-EAST",
    "SOUTH",
    "SOUTH-WEST",
    "WEST",
    "NORTH-WEST",
    "FLOOR",
    "ROOF",
    "ALL WALLS",
    "WALLS+ROOFS",
    "UNDERGRND",
    "BUILDING",
}
NUMBER_PATTERN = re.compile(r"-?[\d,]+(?:\.\d*)?")
CONDITIONED_FLOOR_AREA_PATTERN = re.compile(r"CONDITIONED FLOOR AREA\s*=\s*([\d,]+(?:\.\d+)?)\s+SQFT", re.IGNORECASE)
LV_D_SUMMARY_ROW_PATTERN = re.compile(
    r"^\s*([A-Z][A-Z\-\+\s]+?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
    r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*$"
)
LV_I_ROW_PATTERN = re.compile(
    r"^\s*(.+?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\d+)\s+(DELAYED|QUICK)\s+(\d+)\s*$"
)
LV_I_UVALUE_UNIT_PATTERN = re.compile(r"U-VALUE\s*\(([^\)]+)\)", re.IGNORECASE)
LS_A_LOAD_UNIT_PATTERN = re.compile(r"COOLING LOAD\s*\(([^\)]+)\)", re.IGNORECASE)
def _clean_number(value: str) -> float:
    return float(value.replace(",", ""))
def _parse_values_line(line: str) -> tuple[str, List[float]]:
    stripped = line.strip()
    if not stripped:
        raise ValueError("Expected values line but got blank line.")
    unit = stripped.split()[0]
    numbers = [_clean_number(token) for token in NUMBER_PATTERN.findall(line)]
    if len(numbers) != len(END_USE_COLUMNS):
        raise ValueError(
            f"Expected {len(END_USE_COLUMNS)} numeric BEPS columns but found {len(numbers)} in line: {line!r}"
        )
    return unit, numbers
def extract_beps_report(sim_text: str) -> Dict[str, object]:
    """Parse BEPS and return electricity/natural-gas totals for each end-use column."""
    lines = sim_text.splitlines()
    report_start = next((i for i, line in enumerate(lines) if "REPORT- BEPS" in line.upper()), None)
    if report_start is None:
        raise ValueError("Could not find 'REPORT- BEPS' in the SIM file.")
    section_lines = lines[report_start : report_start + 300]
    rows: Dict[str, Dict[str, object]] = {}
    idx = 0
    while idx < len(section_lines):
        line = section_lines[idx].strip()
        upper = line.upper()
        if upper.startswith("REPORT-") and idx > 0:
            break
        is_electric = "ELECTRICITY" in upper
        is_gas = "NATURAL-GAS" in upper or "NATURAL GAS" in upper
        if not (is_electric or is_gas):
            idx += 1
            continue
        row_name = " ".join(line.split())
        j = idx + 1
        while j < len(section_lines) and not section_lines[j].strip():
            j += 1
        if j >= len(section_lines):
            raise ValueError(f"Missing values line for BEPS row '{row_name}'.")
        unit, values = _parse_values_line(section_lines[j])
        rows[row_name] = {
            "fuel_type": "electricity" if is_electric else "natural_gas",
            "unit": unit,
            "values": dict(zip(END_USE_COLUMNS, values)),
        }
        idx = j + 1
    if not rows:
        raise ValueError("No electricity or natural-gas rows were parsed from BEPS.")
    totals = {
        "electricity": {col: 0.0 for col in END_USE_COLUMNS},
        "natural_gas": {col: 0.0 for col in END_USE_COLUMNS},
    }
    units = {"electricity": None, "natural_gas": None}
    for row in rows.values():
        fuel_type = row["fuel_type"]
        row_unit = row["unit"]
        if units[fuel_type] is None:
            units[fuel_type] = row_unit
        elif units[fuel_type] != row_unit:
            raise ValueError(
                f"Inconsistent units for {fuel_type}: saw both '{units[fuel_type]}' and '{row_unit}'."
            )
        for col, value in row["values"].items():
            totals[fuel_type][col] += value
    return {
        "report": "BEPS",
        "columns": END_USE_COLUMNS,
        "rows": rows,
        "totals_by_fuel": {
            "electricity": {"unit": units["electricity"], "by_end_use": totals["electricity"]},
            "natural_gas": {"unit": units["natural_gas"], "by_end_use": totals["natural_gas"]},
        },
    }
def extract_lv_b_spaces(sim_text: str) -> Dict[str, object]:
    """Extract unique LV-B spaces, grouping label, requested attributes, and conditioned floor area."""
    lines = sim_text.splitlines()
    in_lvb = False
    current_group = None
    spaces: Dict[str, Dict[str, object]] = {}
    for raw_line in lines:
        stripped = raw_line.strip()
        upper = stripped.upper()
        if "REPORT- LV-B" in upper:
            in_lvb = True
            continue
        if in_lvb and upper.startswith("REPORT-") and "REPORT- LV-B" not in upper:
            in_lvb = False
        if not in_lvb:
            continue
        if upper.startswith("SPACES ON FLOOR:"):
            current_group = stripped
            continue
        if (
            not stripped
            or upper.startswith("NUMBER OF SPACES")
            or "SPACE*FLOOR" in upper
            or upper.startswith("BUILDING TOTALS")
            or "SPACE" == upper
            or set(stripped) <= {"-", "=", "+"}
        ):
            continue
        parts = [part.strip() for part in re.split(r"\s{2,}", raw_line.strip()) if part.strip()]
        if len(parts) < 11:
            continue
        space_name = parts[0]
        _space_floor_multiplier = parts[1]
        space_type = parts[2]
        _azimuth = parts[3]
        lights = parts[4]
        people = parts[5]
        equip = parts[6]
        infiltration_method = parts[7]
        ach = parts[8]
        area_sqft = parts[9]
        volume_cuft = parts[10]
        if space_type not in {"INT", "EXT"}:
            continue
        try:
            float(_space_floor_multiplier)
            float(_azimuth)
            float(lights)
            float(people)
            float(equip)
            float(ach)
            float(area_sqft)
            float(volume_cuft)
        except ValueError:
            continue
        normalized_name = " ".join(space_name.split())
        if normalized_name in spaces:
            continue
        spaces[normalized_name] = {
            "group": current_group,
            "space_type": space_type,
            "lights_w_per_sqft": float(lights),
            "people": float(people),
            "equip_w_per_sqft": float(equip),
            "infiltration_method": infiltration_method,
            "ach": float(ach),
            "area_sqft": float(area_sqft),
            "volume_cuft": float(volume_cuft),
            "units": {
                "lights": "WATT/SQFT",
                "equip": "WATT/SQFT",
                "area": "SQFT",
                "volume": "CUFT",
                "ach": "ACH",
            },
        }
    if not spaces:
        raise ValueError("Could not parse any LV-B space rows from the SIM file.")
    conditioned_floor_area_match = CONDITIONED_FLOOR_AREA_PATTERN.search(sim_text)
    conditioned_floor_area = None
    if conditioned_floor_area_match:
        conditioned_floor_area = float(conditioned_floor_area_match.group(1).replace(",", ""))
    return {
        "report": "LV-B",
        "space_count": len(spaces),
        "conditioned_floor_area_sqft": conditioned_floor_area,
        "spaces": spaces,
    }
def extract_lv_d_report(sim_text: str) -> Dict[str, object]:
    """Extract only the final LV-D summary section by major orientation/category."""
    lines = sim_text.splitlines()
    in_lvd = False
    summary_rows: Dict[str, Dict[str, float]] = {}
    for raw_line in lines:
        stripped = raw_line.strip()
        upper = stripped.upper()
        if "REPORT- LV-D" in upper:
            in_lvd = True
            continue
        if in_lvd and upper.startswith("REPORT-") and "REPORT- LV-D" not in upper:
            in_lvd = False
        if not in_lvd:
            continue
        match = LV_D_SUMMARY_ROW_PATTERN.match(raw_line)
        if not match:
            continue
        (
            orientation,
            avg_u_value_windows,
            avg_u_value_walls,
            avg_u_value_walls_plus_windows,
            window_area,
            wall_area,
            window_plus_wall_area,
        ) = match.groups()
        normalized_orientation = " ".join(orientation.split())
        if normalized_orientation not in LV_D_TARGET_ORIENTATIONS:
            continue
        summary_rows[normalized_orientation] = {
            "avg_u_value_windows": float(avg_u_value_windows),
            "avg_u_value_walls": float(avg_u_value_walls),
            "avg_u_value_walls_plus_windows": float(avg_u_value_walls_plus_windows),
            "window_area": float(window_area),
            "wall_area": float(wall_area),
            "window_plus_wall_area": float(window_plus_wall_area),
        }
    if not summary_rows:
        raise ValueError("Could not parse LV-D summary rows from the SIM file.")
    missing = sorted(LV_D_TARGET_ORIENTATIONS.difference(summary_rows.keys()))
    return {
        "report": "LV-D",
        "columns": LV_D_COLUMNS,
        "units": LV_D_UNITS,
        "orientations": summary_rows,
        "missing_orientations": missing,
    }
def extract_lv_i_constructions(sim_text: str) -> Dict[str, object]:
    """Extract LV-I construction names with U-value and number of response factors."""
    lines = sim_text.splitlines()
    in_lvi = False
    constructions: Dict[str, Dict[str, object]] = {}
    section_lines: List[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        upper = stripped.upper()
        if "REPORT- LV-I" in upper:
            in_lvi = True
            continue
        if in_lvi and upper.startswith("REPORT-") and "REPORT- LV-I" not in upper:
            in_lvi = False
        if not in_lvi:
            continue
        section_lines.append(raw_line)
        match = LV_I_ROW_PATTERN.match(raw_line)
        if not match:
            continue
        construction_name = " ".join(match.group(1).split())
        u_value = float(match.group(2))
        response_factors = int(match.group(6))
        constructions[construction_name] = {
            "u_value": u_value,
            "number_of_response_factors": response_factors,
        }
    if not constructions:
        raise ValueError("Could not parse any LV-I construction rows from the SIM file.")
    unit = "BTU/HR-SQFT-F"
    section_text = "\n".join(section_lines)
    unit_match = LV_I_UVALUE_UNIT_PATTERN.search(section_text)
    if unit_match:
        unit = unit_match.group(1).strip()
    return {
        "report": "LV-I",
        "u_value_unit": unit,
        "construction_count": len(constructions),
        "constructions": constructions,
    }
def extract_ls_a_peak_loads(sim_text: str, lv_b_result: Dict[str, object] | None = None) -> Dict[str, object]:
    """Extract LS-A cooling/heating peak loads and associate them with LV-B spaces."""
    if lv_b_result is None:
        lv_b_result = extract_lv_b_spaces(sim_text)
    lv_b_spaces = lv_b_result["spaces"]
    lines = sim_text.splitlines()
    in_lsa = False
    loads_by_space: Dict[str, Dict[str, float]] = {}
    units = "KBTU/HR"
    for raw_line in lines:
        stripped = raw_line.strip()
        upper = stripped.upper()
        if "REPORT- LS-A" in upper:
            in_lsa = True
            continue
        if in_lsa and upper.startswith("REPORT-") and "REPORT- LS-A" not in upper:
            in_lsa = False
        if not in_lsa:
            continue
        unit_match = LS_A_LOAD_UNIT_PATTERN.search(raw_line)
        if unit_match:
            units = unit_match.group(1).strip()
        if (
            not stripped
            or upper.startswith("SPACE NAME")
            or upper.startswith("MULTIPLIER")
            or set(stripped) <= {"-", "=", "+"}
        ):
            continue
        parts = [part.strip() for part in re.split(r"\s{2,}", stripped) if part.strip()]
        if len(parts) < 4:
            continue
        space_name = " ".join(parts[0].split())
        numeric_parts = []
        for token in parts[3:]:
            if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
                numeric_parts.append(float(token))
        if len(numeric_parts) < 2:
            continue
        loads_by_space[space_name] = {
            "cooling_load": numeric_parts[0],
            "heating_load": numeric_parts[1],
        }
    if not loads_by_space:
        raise ValueError("Could not parse any LS-A space peak loads from the SIM file.")
    spaces_with_peak_loads: Dict[str, Dict[str, object]] = {}
    for space_name, space_data in lv_b_spaces.items():
        merged = dict(space_data)
        merged["peak_loads"] = {
            "cooling_load": loads_by_space.get(space_name, {}).get("cooling_load"),
            "heating_load": loads_by_space.get(space_name, {}).get("heating_load"),
            "units": units,
        }
        spaces_with_peak_loads[space_name] = merged
    return {
        "report": "LS-A",
        "load_units": units,
        "space_peak_loads": loads_by_space,
        "spaces_with_peak_loads": spaces_with_peak_loads,
    }
def extract_lv_m_conversions(sim_text: str) -> Dict[str, object]:
    """Extract conversion factors from LV-M and store them for future unit transforms."""
    lines = sim_text.splitlines()
    in_lvm = False
    conversions: Dict[str, Dict[str, float]] = {}
    for raw_line in lines:
        stripped = raw_line.strip()
        upper = stripped.upper()
        if "REPORT- LV-M" in upper:
            in_lvm = True
            continue
        if in_lvm and upper.startswith("REPORT-") and "REPORT- LV-M" not in upper:
            in_lvm = False
        if not in_lvm:
            continue
        parts = [part.strip() for part in re.split(r"\s{2,}", stripped) if part.strip()]
        # Expected: idx, english, factor1, metric, factor2, english2
        if len(parts) < 6:
            continue
        if not parts[0].isdigit():
            continue
        source_unit = parts[1]
        try:
            source_to_target = float(parts[2])
            target_to_source = float(parts[4])
        except ValueError:
            continue
        target_unit = parts[3]
        reverse_unit = parts[5]
        conversions.setdefault(source_unit, {})[target_unit] = source_to_target
        conversions.setdefault(target_unit, {})[reverse_unit] = target_to_source
    if not conversions:
        raise ValueError("Could not parse LV-M unit conversion rows from the SIM file.")
    return {
        "report": "LV-M",
        "conversions": conversions,
        "usage": "Use convert_value(value, from_unit, to_unit, conversions) for future transformations.",
    }
def convert_value(value: float, from_unit: str, to_unit: str, conversions: Dict[str, Dict[str, float]]) -> float:
    """Convert a value between units using LV-M conversion factors (supports chained conversions)."""
    if from_unit == to_unit:
        return value
    visited = set()
    queue: List[tuple[str, float]] = [(from_unit, value)]
    while queue:
        current_unit, current_value = queue.pop(0)
        if current_unit in visited:
            continue
        visited.add(current_unit)
        for next_unit, factor in conversions.get(current_unit, {}).items():
            next_value = current_value * factor
            if next_unit == to_unit:
                return next_value
            if next_unit not in visited:
                queue.append((next_unit, next_value))
    raise ValueError(f"No conversion path found from '{from_unit}' to '{to_unit}'.")
def extract_es_d_energy_cost_summary(sim_text: str) -> Dict[str, object]:
    """Extract utility-rate virtual rate, metered unit, and total charge from ES-D."""
    lines = sim_text.splitlines()
    in_esd = False
    utility_rates: Dict[str, Dict[str, object]] = {}
    for raw_line in lines:
        stripped = raw_line.strip()
        upper = stripped.upper()
        if "REPORT- ES-D" in upper:
            in_esd = True
            continue
        if in_esd and upper.startswith("REPORT-") and "REPORT- ES-D" not in upper:
            in_esd = False
        if not in_esd:
            continue
        if (
            not stripped
            or upper.startswith("UTILITY-RATE")
            or upper.startswith("METERED")
            or upper.startswith("ENERGY COST/")
            or set(stripped) <= {"-", "=", "+"}
        ):
            continue
        parts = [part.strip() for part in re.split(r"\s{2,}", stripped) if part.strip()]
        if len(parts) < 6:
            continue
        utility_rate = parts[0]
        metered_energy = parts[-4]
        total_charge_str = parts[-3]
        virtual_rate_str = parts[-2]
        metered_tokens = metered_energy.split()
        if len(metered_tokens) < 2:
            continue
        unit = metered_tokens[-1]
        try:
            total_charge = float(total_charge_str.replace(",", ""))
            virtual_rate = float(virtual_rate_str.replace(",", ""))
        except ValueError:
            continue
        utility_rates[utility_rate] = {
            "unit": unit,
            "total_charge": total_charge,
            "total_charge_unit": "$",
            "virtual_rate": virtual_rate,
            "virtual_rate_unit": "$/Unit",
        }
    if not utility_rates:
        raise ValueError("Could not parse ES-D utility-rate rows from the SIM file.")
    return {
        "report": "ES-D",
        "utility_rates": utility_rates,
    }
def extract_ps_h_details(sim_text: str) -> Dict[str, object]:
    """Extract PS-H loop, pump, and equipment sizing details."""
    lines = sim_text.splitlines()
    loops: Dict[str, Dict[str, object]] = {}
    pumps: Dict[str, Dict[str, object]] = {}
    equipment: Dict[str, Dict[str, object]] = {}
    report_indices = [i for i, line in enumerate(lines) if "REPORT- PS-H" in line.upper()]
    for start in report_indices:
        line = lines[start]
        name_match = re.search(r"REPORT-\s*PS-H\s+Loads and Energy Usage for\s+(.+?)\s+WEATHER FILE", line, re.IGNORECASE)
        if not name_match:
            continue
        report_name = " ".join(name_match.group(1).split())
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].strip().upper().startswith("REPORT-"):
                end = j
                break
        block = lines[start:end]
        block_text = "\n".join(block)
        if "DETAILED SIZING INFORMATION" in block_text:
            units_line_idx = next((i for i, b in enumerate(block) if "(MBTU/HR)" in b and "(HOURS)" in b and "(BTU/BTU)" in b), None)
            if units_line_idx is not None:
                units = re.findall(r"\(([^\)]+)\)", block[units_line_idx])
                row = None
                for k in range(units_line_idx + 1, min(units_line_idx + 20, len(block))):
                    if "----" in block[k]:
                        continue
                    parts = [part.strip() for part in re.split(r"\s{2,}", block[k].strip()) if part.strip()]
                    if len(parts) >= 8 and re.fullmatch(r"-?\d+(?:\.\d+)?", parts[1]):
                        row = parts
                        break
                if row:
                    equipment[report_name] = {
                        "capacity": float(row[1]),
                        "start_up": float(row[2]),
                        "electric": float(row[3]),
                        "heat_eir": float(row[4]),
                        "aux_elec": float(row[5]),
                        "fuel": float(row[6]),
                        "heat_hir": float(row[7]),
                        "units": {
                            "capacity": units[0] if len(units) > 0 else "MBTU/HR",
                            "start_up": units[1] if len(units) > 1 else "HOURS",
                            "electric": units[2] if len(units) > 2 else "KW",
                            "heat_eir": units[3] if len(units) > 3 else "BTU/BTU",
                            "aux_elec": units[4] if len(units) > 4 else "KW",
                            "fuel": units[5] if len(units) > 5 else "MBTU/HR",
                            "heat_hir": units[6] if len(units) > 6 else "BTU/BTU",
                        },
                    }
        elif "HEATING     COOLING      LOOP" in block_text:
            # first PS-H loop instance table at top
            units_line_idx = next((i for i, b in enumerate(block) if "(MBTU/HR)" in b and "(GPM" in b and "(FT)" in b), None)
            if units_line_idx is None:
                continue
            units = re.findall(r"\(([^\)]+)\)", block[units_line_idx])
            value_parts = None
            for k in range(units_line_idx + 1, min(units_line_idx + 12, len(block))):
                candidate = block[k].strip()
                if not candidate or '----' in candidate:
                    continue
                parts = candidate.split()
                if len(parts) >= 10 and all(re.fullmatch(r"-?\d+(?:\.\d+)?", p) for p in parts[:10]):
                    value_parts = parts[:10]
                    break
            if value_parts:
                loops[report_name] = {
                    "heating_capacity": float(value_parts[0]),
                    "cooling_capacity": float(value_parts[1]),
                    "loop_flow": float(value_parts[2]),
                    "total_head": float(value_parts[3]),
                    "loop_volume": float(value_parts[8]),
                    "units": {
                        "heating_capacity": units[0] if len(units) > 0 else "MBTU/HR",
                        "cooling_capacity": units[1] if len(units) > 1 else "MBTU/HR",
                        "loop_flow": units[2] if len(units) > 2 else "GPM",
                        "total_head": units[3] if len(units) > 3 else "FT",
                        "loop_volume": units[8] if len(units) > 8 else "GAL",
                    },
                }
        elif "CAPACITY               MECHANICAL" in block_text and "ATTACHED TO" in block_text:
            header_idx = next((i for i, b in enumerate(block) if "ATTACHED TO" in b and "(GPM" in b and "(KW)" in b), None)
            if header_idx is None:
                continue
            units_line = block[header_idx]
            units = re.findall(r"\(([^\)]+)\)", units_line)
            row = None
            for k in range(header_idx + 1, min(header_idx + 12, len(block))):
                candidate = block[k].strip()
                if not candidate or '----' in candidate:
                    continue
                parts = [part.strip() for part in re.split(r"\s{2,}", candidate) if part.strip()]
                if len(parts) >= 8 and re.fullmatch(r"-?\d+(?:\.\d+)?", parts[1]):
                    row = parts
                    break
            if row:
                pumps[report_name] = {
                    "attached_to": row[0],
                    "flow": float(row[1]),
                    "head": float(row[2]),
                    "capacity_control": row[4],
                    "power": float(row[5]),
                    "mechanical_efficiency": float(row[6]),
                    "motor_efficiency": float(row[7]),
                    "units": {
                        "flow": units[0] if len(units) > 0 else "GPM",
                        "head": units[1] if len(units) > 1 else "FT",
                        "capacity_control": "unitless",
                        "power": units[3] if len(units) > 3 else "KW",
                        "mechanical_efficiency": units[4] if len(units) > 4 else "FRAC",
                        "motor_efficiency": units[5] if len(units) > 5 else "FRAC",
                    },
                }
    if not (loops or pumps or equipment):
        raise ValueError("Could not parse PS-H loop/pump/equipment details from the SIM file.")
    return {
        "report": "PS-H",
        "loops": loops,
        "pumps": pumps,
        "equipment": equipment,
    }
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract BEPS, LV-B, LV-D, LV-I, LS-A, LV-M, ES-D, and PS-H report data from an eQuest SIM file."
    )
    parser.add_argument("sim_file", type=Path, help="Path to the eQuest .SIM file")
    parser.add_argument(
        "--report",
        choices=["beps", "lv-b", "lv-d", "lv-i", "ls-a", "lv-m", "es-d", "ps-h", "all"],
        default="all",
        help="Which report(s) to extract (default: all)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level for output (default: 2)",
    )
    args = parser.parse_args()
    sim_text = args.sim_file.read_text(errors="ignore")
    if args.report == "beps":
        result = extract_beps_report(sim_text)
    elif args.report == "lv-b":
        result = extract_lv_b_spaces(sim_text)
    elif args.report == "lv-d":
        result = extract_lv_d_report(sim_text)
    elif args.report == "lv-i":
        result = extract_lv_i_constructions(sim_text)
    elif args.report == "ls-a":
        result = extract_ls_a_peak_loads(sim_text)
    elif args.report == "lv-m":
        result = extract_lv_m_conversions(sim_text)
    elif args.report == "es-d":
        result = extract_es_d_energy_cost_summary(sim_text)
    elif args.report == "ps-h":
        result = extract_ps_h_details(sim_text)
    else:
        lv_b_result = extract_lv_b_spaces(sim_text)
        lv_m_result = extract_lv_m_conversions(sim_text)
        result = {
            "beps": extract_beps_report(sim_text),
            "lv_b_spaces": lv_b_result,
            "lv_d": extract_lv_d_report(sim_text),
            "lv_i": extract_lv_i_constructions(sim_text),
            "ls_a_peak_loads": extract_ls_a_peak_loads(sim_text, lv_b_result=lv_b_result),
            "lv_m": lv_m_result,
            "es_d": extract_es_d_energy_cost_summary(sim_text),
            "ps_h": extract_ps_h_details(sim_text),
        }
    print(json.dumps(result, indent=args.indent))
if __name__ == "__main__":
    main()
