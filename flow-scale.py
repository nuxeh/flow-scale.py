import re
import argparse
import sys

def extract_z(line):
    match = re.search(r'\bZ([-+]?[0-9]*\.?[0-9]+)', line)
    return float(match.group(1)) if match else None

def process_gcode_line(line, flow_ratio, current_z, z_start, z_end):
    if z_start is not None and current_z is not None:
        if current_z < z_start or (z_end is not None and current_z > z_end):
            return line

    # Match G0 or G1 lines that include an E value
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
    parser = argparse.ArgumentParser(description="Scale G-code E values by flow ratio within Z-height range.")
    parser.add_argument('--in', dest='infile', required=True, help='Input G-code file')
    parser.add_argument('--out', dest='outfile', required=True, help='Output G-code file')
    parser.add_argument('--flow-ratio', type=float, required=True, help='Flow ratio to scale E values')
    parser.add_argument('--z-start', type=float, default=None, help='Start Z-height (inclusive)')
    parser.add_argument('--z-end', type=float, default=None, help='End Z-height (inclusive)')
    parser.add_argument('--force', action='store_true', help='Force processing even if G92 E0 safety check fails')

    args = parser.parse_args()

    current_z = None
    extrusion_mode = 'absolute'  # default mode
    g92_e0_count = 0
    input_lines = []

    # First pass: read and analyze file
    with open(args.infile, 'r') as fin:
        for line in fin:
            input_lines.append(line)
            if 'M82' in line:
                extrusion_mode = 'absolute'
            elif 'M83' in line:
                extrusion_mode = 'relative'
            elif re.search(r'\bG92\s+E0\b', line):
                g92_e0_count += 1

    if extrusion_mode == 'absolute' and g92_e0_count < 2 and not args.force:
        print("❌ ERROR: Detected M82 (absolute extrusion) with fewer than 2 G92 E0 resets.")
        print("Scaling E values directly may lead to incorrect extrusion.")
        print("Use --force to override this check if you know what you're doing.")
        sys.exit(1)

    # Second pass: process and write output
    with open(args.outfile, 'w') as fout:
        for line in input_lines:
            z = extract_z(line)
            if z is not None:
                current_z = z
            fout.write(process_gcode_line(line, args.flow_ratio, current_z, args.z_start, args.z_end))

if __name__ == '__main__':
    main()
