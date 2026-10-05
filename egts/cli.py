"""CLI bridge: reads hex file, writes CSV rows. Called by VBA macro via Shell()."""
import sys
import csv

from .parser import parse_hex


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    if len(args) < 2:
        print("Usage: egts_cli.py <input_hex_file> <output_csv_file>")
        sys.exit(1)

    with open(args[0], "r") as f:
        hex_str = f.read().strip()

    rows, err = parse_hex(hex_str)

    with open(args[1], "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Layer", "Field", "Offset", "Size", "Hex",
                         "Raw", "Decoded", "Desc", "Editable"])
        for r in rows:
            writer.writerow([
                r.layer, r.field, r.offset, r.size, r.hex_val,
                str(r.raw) if not isinstance(r.raw, str) else r.raw,
                r.decoded, r.desc,
                "Y" if r.editable else "N",
            ])

    if err:
        with open(args[1], "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                ["ERROR", "", "", "", "", "", err, "", "N"])


if __name__ == "__main__":
    main()
