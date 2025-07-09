# flow_scale

A post-processing script for scaling extrusion flow in G-code (E values) based on configurable Z-height or layer ranges. Works with absolute or relative extrusion, and can be integrated into slicers like OrcaSlicer, SuperSlicer, Bambu Studio, and others.

FEATURES

- Scale E values (extrusion flow) by a custom ratio
- Apply changes only to specific Z-height or layer ranges
- Detect layer height from slicer environment variables
- Accepts file path from CLI, environment, or positional argument
- --inplace option to modify input file directly
- --force mode to override extrusion safety checks
- Debug mode with CLI (--debug) and file output (--debug-file)

USAGE

    flow_scale.py -r <ratio> [options] [input.gcode]

OPTIONS

  -i, --in                 Input G-code file
  -o, --out                Output G-code file (default: stdout)
  -r, --flow-ratio         REQUIRED. Flow scale factor (e.g., 0.9, 1.05)
  -z, --z-start            Z-height start (inclusive)
  -Z, --z-end              Z-height end (inclusive)
  -l, --layers             Layer range (e.g., 3 or 2:5)
  -L, --layer-height       Layer height in mm (if not set by slicer env)
  -f, --force              Disable G92 E0 safety check
  -p, --inplace            Overwrite input file
  -d, --debug              Print debug info to stderr
  -D, --debug-file [PATH]  Write debug info to file (default: /tmp/flow_scale_debug.txt)
  input.gcode              Optional positional input path (fallback if --in/env not set)

SLICER INTEGRATION

This script supports environment variables from common slicers:

  OrcaSlicer:
    - ORCASLICER_LAYER_HEIGHT
    - ORCASLICER_GCODE_OUTPUT_PATH

  SuperSlicer:
    - SUPERSLICER_LAYER_HEIGHT
    - SUPERSLICER_GCODE_OUTPUT_PATH

  PrusaSlicer:
    - SLIC3R_LAYER_HEIGHT
    - SLIC3R_PP_OUTPUT_NAME

  Bambu Studio:
    - BAMBU_LAYER_HEIGHT
    - BAMBU_GCODE_PATH

DEBUG INFO

Enable with:

    flow_scale.py -r 1.03 -i input.gcode -o output.gcode --debug

Or write to file:

    flow_scale.py -r 1.03 -i input.gcode -o output.gcode --debug-file

Debug includes:
  - Input/output paths
  - Z/layer range
  - Layer height
  - G92 E0 resets counted
  - Total lines and percent modified

REQUIREMENTS

- Python 3.6+

LICENSE

MIT License
