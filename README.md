# eQuest-Simulation-Extraction
This is a python script that can be used to output data from the simulation from eQuest simulation files.

This repository includes a Python utility (`equest_extractor.py`) to extract **BEPS**, **LV-B**, **LV-D**, **LV-I**, **LS-A**, **LV-M**, **ES-D**, and **PS-H** report data from an eQuest `.SIM` file.

It also supports Power Automate-style workbook actions against **Master Room List → Space Type Table** in `Building Performance Assumptions.xlsm` using `--model-run-type`:
- `Baseline`: writes LV-B space names and areas into the table.
- Any non-baseline type (e.g., `Proposed`, `ECM-1`): compares LV-B space names/areas against existing table values and returns a boolean match result.

It also supports updating **ECM Data** tables from BEPS + ES-D based on `--model-run-type` for:
- `Baseline`
- `Proposed`
- `ECM-1` to `ECM-7`

`Baseline-2` and `Baseline-3` are intentionally ignored.

In ECM Data population, these columns are intentionally left blank unless future mapping is provided:
`Fans Process`, `Fans Parking Garage`, `Data Centre Equipment`, `Cooking`, `Elevators/Escalators`, `CHP`, `Humidification`, `Other Processes`.

## BEPS extraction
- Extracts BEPS fuel rows and totals by fuel/end-use.

## LV-B extraction
- Extracts unique spaces and key space attributes.

## LV-D extraction
- Extracts the final LV-D orientation summary table.

## LV-I extraction
- Extracts each construction name with:
  - `u_value`
  - `number_of_response_factors`
- Returns `u_value_unit` (e.g., `BTU/HR-SQFT-F`).

## LS-A extraction
- Extracts peak load values by space from `REPORT- LS-A Space Peak Loads Summary`:
  - `cooling_load`
  - `heating_load`
- Stores load units (e.g., `KBTU/HR`).
- Associates these peak loads with the spaces extracted from LV-B (`spaces_with_peak_loads`).

## LV-M extraction
- Extracts conversion factors from `REPORT- LV-M DOE-2.2 Units Conversion Table`.
- Stores conversions in a dictionary for later use.
- Includes helper `convert_value(value, from_unit, to_unit, conversions)` to convert values now or later.

## ES-D extraction
- Extracts utility-rate summary values from `REPORT- ES-D Energy Cost Summary`.
- Returns for each utility-rate:
  - `virtual_rate` and `virtual_rate_unit` (`$/Unit`)
  - `unit` from the `METERED ENERGY UNITS/YR` field (e.g., `KWH`, `THERM`)
  - `total_charge` and `total_charge_unit` (`$`)

## PS-H extraction
- Extracts equipment/loop/pump-level PS-H details.
- Loops: heating capacity, cooling capacity, loop flow, total head, loop volume + units.
- Pumps: attached-to, flow, head, capacity control, power, mechanical efficiency, motor efficiency + units.
- Equipment (from the second PS-H instance detailed sizing): capacity, start-up, electric, heat EIR, aux elec, fuel, heat HIR + units.

## Usage

```bash
python equest_extractor.py /path/to/file.SIM
python equest_extractor.py /path/to/file.SIM --report beps
python equest_extractor.py /path/to/file.SIM --report lv-b
python equest_extractor.py /path/to/file.SIM --report lv-d
python equest_extractor.py /path/to/file.SIM --report lv-i
python equest_extractor.py /path/to/file.SIM --report ls-a
python equest_extractor.py /path/to/file.SIM --report lv-m
python equest_extractor.py /path/to/file.SIM --report es-d
python equest_extractor.py /path/to/file.SIM --report ps-h
python equest_extractor.py /path/to/file.SIM --report all

# Populate Master Room List > Space Type Table (Space Name + Area)
python equest_extractor.py /path/to/file.SIM \
  --populate-master-room-list /path/to/Building\ Performance\ Assumptions.xlsm \
  --model-run-type Baseline \
  --output-workbook /path/to/Building\ Performance\ Assumptions.updated.xlsm

# Validate against existing Baseline data (returns space_type_table_match true/false)
python equest_extractor.py /path/to/file.SIM \
  --populate-master-room-list /path/to/Building\ Performance\ Assumptions.xlsm \
  --model-run-type ECM-1

# Populate ECM Data section for model run type (Baseline/Proposed/ECM-1..ECM-7)
python equest_extractor.py /path/to/file.SIM \
  --update-ecm-data /path/to/Building\ Performance\ Assumptions.xlsm \
  --model-run-type ECM-3 \
  --output-workbook /path/to/Building\ Performance\ Assumptions.updated.xlsm
```

## Power Automate + Teams card input

If you collect **Model Run Type** from a Teams Adaptive Card, pass it directly into Python using either CLI args or an environment variable:

1. In Power Automate, add **Post adaptive card and wait for a response**.
2. Read the response field (for example: `modelRunType`).
3. In the Python execution step, pass that value as:

### Option A: CLI argument (recommended)
```bash
python equest_extractor.py "<SIM_PATH>" \
  --populate-master-room-list "<XLSM_PATH>" \
  --model-run-type "<MODEL_RUN_TYPE_FROM_TEAMS>" \
  --output-workbook "<OUTPUT_XLSM_IF_BASELINE>"
```

### Option B: Environment variable
Set environment variable `MODEL_RUN_TYPE` in the Power Automate step and run:
```bash
python equest_extractor.py "<SIM_PATH>" \
  --populate-master-room-list "<XLSM_PATH>" \
  --output-workbook "<OUTPUT_XLSM_IF_BASELINE>"
```

`equest_extractor.py` resolves model run type in this order:  
1) `--model-run-type` argument, 2) `MODEL_RUN_TYPE` env var, 3) default `"Baseline"`.
