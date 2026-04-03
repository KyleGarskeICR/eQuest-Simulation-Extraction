# eQuest-Simulation-Extraction
This is a python script that can be used to output data from the simulation from eQuest simulation files.

This repository includes a Python utility (`equest_extractor.py`) to extract **BEPS**, **LV-B**, **LV-D**, **LV-I**, **LS-A**, **LV-M**, **ES-D**, and **PS-H** report data from an eQuest `.SIM` file.

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
```
