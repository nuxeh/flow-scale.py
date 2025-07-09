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

def get_input_path_from_env():
    candidates = [
        'ORCASLICER_GCODE_OUTPUT_PATH',
        'SUPERSLICER_GCODE_OUTPUT_PATH',
        'SLIC3R_PP_OUTPUT_NAME',
        'BAMBU_GCODE_PATH'
    ]
    for var in candidates:
        val = os.environ.get(var)
        if val and os.path.exists(val):
            return val
    return None

def process_gcode_line(line, flow_ratio, current_z, z_start, z_end,
                       current_layer, layer_start, layer_end, use_layer_mode):
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

def write_debug_output(params, to_stderr=False, to_file_path=None):
    lines = ["=== flow_scale Debug Info ==="]
    for key, value in params.items():
        lines.append(f"{key}: {value}")
    output = "\n".join(lines) + "\n"

    if to_stderr:
        print(output, file=sys.stderr)
    if to_file_path:
        try:
            with open(to_file_path, 'w') as f:
                f.write(output)
        except Exception as e:
            print(f"⚠️ Could not write debug file: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="flow_scale: Scale G-code E values by flow ratio within Z or layer range."
    )
    parser.add_argument('-i', '--in', dest='infile', help='Input G-code file')
    parser.add_argument('-o', '--out', dest='outfile', default='-', help='Output G-code file (default: stdout)')
    parser.add_argument('-r', '--flow-ratio', type=float, required=True, help='Flow ratio to scale E values')
    parser.add_argument('-z', '--z-start', type=float, default=None, help='Start Z-height (inclusive)')
    parser.add_argument('-Z', '--z-end', type=float, default=None, help='End Z-height (inclusive)')
    parser.add_argument('-l', '--layers', type=str, help='Layer range (e.g., 2:5 or 3)')
    parser.add_argument('-L', '--layer-height', type=float, help='Layer height in mm (optional if detectable)')
    parser.add_argument('-f', '--force', action='store_true', help='Force processing even if G92 E0 safety check fails')
    parser.add_argument('-p', '--inplace', action='store_true', help='Modify the input file in-place')
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug info to stderr')
    parser.add_argument('-D', '--debug-file', nargs='?', const='/tmp/flow_scale_debug.txt',
                        help='Write debug info to file (default: /tmp/flow_scale_debug.txt)')
    parser.add_argument('positional_infile', nargs='?', help='Input file path (used only if --in and env vars not set)')
    args = parser.parse_args()

    if args.infile:
        infile = args.infile
    else:
        env_path = get_input_path_from_env()
        if env_path:
            infile = env_path
        elif args.positional_infile:
            infile = args.positional_infile
        else:
            infile = '-'

    if args.inplace:
        if infile == '-':
            print("❌ ERROR: Cannot use --inplace with stdin input.", file=sys.stderr)
            sys.exit(1)
        outfile = infile
    else:
        outfile = args.outfile

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

    modified_lines = 0
    output_stream = sys.stdout if outfile == '-' else open(outfile, 'w')
    with output_stream as fout:
        for line in input_lines:
            z = extract_z(line)
            if z is not None:
                current_z = z

            current_layer = None
            if use_layer_mode and current_z is not None and layer_height:
                current_layer = int(round(current_z / layer_height))

            new_line = process_gcode_line(
                line, args.flow_ratio,
                current_z, args.z_start, args.z_end,
                current_layer, layer_start, layer_end,
                use_layer_mode
            )
            if new_line != line:
                modified_lines += 1
            fout.write(new_line)

    if args.debug or args.debug_file:
        total_lines = len(input_lines)
        percent_modified = (modified_lines / total_lines) * 100 if total_lines > 0 else 0.0
        debug_data = {
            'Input file': infile,
            'Output file': outfile,
            'Flow ratio': args.flow_ratio,
            'Inplace': args.inplace,
            'Z-start': args.z_start,
            'Z-end': args.z_end,
            'Layer mode': use_layer_mode,
            'Layer start': layer_start,
            'Layer end': layer_end,
            'Layer height': layer_height,
            'Extrusion mode': extrusion_mode,
            'G92 E0 resets': g92_e0_count,
            'Total lines': total_lines,
            'Lines modified': modified_lines,
            'Modified %': f"{percent_modified:.2f}%",
        }
        write_debug_output(debug_data, to_stderr=args.debug, to_file_path=args.debug_file)

if __name__ == '__main__':
    main()
