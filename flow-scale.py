#!/usr/bin/env python3
import re
import argparse
import sys
import os

def extract_z(line):
    match = re.search(r'\bZ([-+]?[0-9]*\.?[0-9]+)', line)
    return float(match.group(1)) if match else None

def get_layer_height_from_env():
    candidates = [
        'ORCASLICER_LAYER_HEIGHT',
        'SUPERSLICER_LAYER_HEIGHT',
        'SLIC3R_LAYER_HEIGHT',
        'BAMBU_LAYER_HEIGHT',
        'LAYER_HEIGHT',
        'layer_height',
        'LAYERHEIGHT'
    ]
    for var in candidates:
        val = os.environ.get(var)
        if val:
            try:
                return float(val)
            except ValueError:
                continue
    return None

def process_gcode_line(line, flow_ratio, current_z, z_start, z_end, current_layer, layer_start, layer_end, use_layer_mode):
    if use_layer_mode and current_layer is not None:
        if current_layer < layer_start or (layer_end is not None and current_layer > layer_end):
            return line
    elif not use_layer_mode and z_start is not None and current_z is not None:
        if current_z < z_start or (z_end is not None and current_z > z_end):
            return line

    match = re.search(r'^([Gg]0|[Gg]1)(.*?\s)(E)([-+]?[0-9]*\.?[0-9]+)', line)
    if match:
        cmd = match.group(1)
        middle = match.group(2)
        e_val = float(match.group(4))
        new_e_val = e_val * flow_ratio
        new_line = f"{cmd}{middle}E{new_e_val:.5f}"
        rest = line[match.end():]
        return new_line + rest
    return line

def main():
    parser = argparse.ArgumentParser(
        description="Scale G-code E values by flow ratio within Z or layer range."
    )
    parser.add_argument('--in', dest='infile', help='Input G-code file')
    parser.add_argument('--out', dest='outfile', default='-', help='Output G-code file (default: stdout)')
    parser.add_argument('--flow-ratio', type=float, required=True, help='Flow ratio to scale E values')
    parser.add_argument('--z-start', type=float, default=None, help='Start Z-height (inclusive)')
    parser.add_argument('--z-end', type=float, default=None, help='End Z-height (inclusive)')
    parser.add_argument('--layers', type=str, help='Layer range (e.g., 2:5 or 3)')
    parser.add_argument('--layer-height', type=float, help='Layer height in mm (optional if detectable)')
    parser.add_argument('--force', action='store_true', help='Force processing even if G92 E0 safety check fails')
    parser.add_argument('positional_infile', nargs='?', help='Positional input file path (used if --in not given)')

    args = parser.parse_args()

    # Fallback logic: --in takes precedence, otherwise use positional arg
    #infile = ''
    if args.infile:
        infile = args.infile
    elif args.positional_infile:
        infile = args.positional_infile
    else:
        infile = '-'  # stdin

    use_layer_mode = args.layers is not None
    layer_start = layer_end = None
    if use_layer_mode:
        if ':' in args.layers:
            parts = args.layers.split(':')
            layer_start = int(parts[0])
            layer_end = int(parts[1])
        else:
            layer_start = int(args.layers)
            layer_end = layer_start

    current_z = None
    extrusion_mode = 'absolute'
    g92_e0_count = 0
    input_lines = []

    input_stream = sys.stdin if infile == '-' else open(infile, 'r')
    with input_stream as fin:
        for line in fin:
            input_lines.append(line)
            if 'M82' in line:
                extrusion_mode = 'absolute'
            elif 'M83' in line:
                extrusion_mode = 'relative'
            elif re.search(r'\bG92\s+E0\b', line):
                g92_e0_count += 1

    layer_height = args.layer_height or get_layer_height_from_env()
    if use_layer_mode and layer_height is None:
        print("❌ ERROR: Layer height not provided and could not be found in environment.", file=sys.stderr)
        sys.exit(1)

    if extrusion_mode == 'absolute' and g92_e0_count < 2 and not args.force:
        print("❌ ERROR: Detected M82 (absolute extrusion) with fewer than 2 G92 E0 resets.", file=sys.stderr)
        print("Scaling E values directly may lead to incorrect extrusion.", file=sys.stderr)
        print("Use --force to override this check if you know what you're doing.", file=sys.stderr)
        sys.exit(1)

    output_stream = sys.stdout if args.outfile == '-' else open(args.outfile, 'w')
    with output_stream as fout:
        for line in input_lines:
            z = extract_z(line)
            if z is not None:
                current_z = z

            current_layer = None
            if use_layer_mode and current_z is not None and layer_height > 0:
                current_layer = int(round(current_z / layer_height))

            fout.write(process_gcode_line(
                line, args.flow_ratio,
                current_z, args.z_start, args.z_end,
                current_layer, layer_start, layer_end,
                use_layer_mode
            ))

if __name__ == '__main__':
    main()
