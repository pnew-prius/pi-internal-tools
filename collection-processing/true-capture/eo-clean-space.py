"""Convert a POSPac EO text file (event1_eo_Mission N.txt) to a gps-imu-data CSV.

Replaces EO-cleanup.py. Fields are split on whitespace instead of being cut out
at fixed character positions, so the image name can be any length and negative
Omega/Phi/Kappa values keep their minus sign.

Run with no arguments to pick the EO file in a dialog, or:
    python eo-clean-space.py <event_eo.txt> [<output.csv>]
"""
import datetime
import os
import sys

# EO record: ID, EVENT, TIME, EASTING, NORTHING, ELLIPSOID HEIGHT, OMEGA, PHI, KAPPA, LAT, LONG
NUMERIC_FIELDS = 10
HEADER = "Filename, Longitude, Latitude, Altitude, Omega, Phi, Kappa, HorAcc, VertAcc\n"


def parse_line(line):
    """Return (name, lon, lat, alt, omega, phi, kappa) for a data row, else None."""
    parts = line.rsplit(None, NUMERIC_FIELDS)  # split from the right: the name may contain spaces
    if len(parts) != NUMERIC_FIELDS + 1:
        return None
    name = parts[0].strip()
    values = parts[1:]
    try:
        [float(v) for v in values]
    except ValueError:
        return None
    if not name:
        return None
    event, time, easting, northing, height, omega, phi, kappa, lat, lon = values
    return name, lon, lat, str(float(height)), omega, phi, kappa


def convert(eo_path, csv_path):
    rows = []
    expected = None
    with open(eo_path, 'r') as eo:
        for line in eo:
            row = parse_line(line)
            if row:
                rows.append(row)
                expected = int(line.rsplit(None, NUMERIC_FIELDS)[1])  # EVENT number of the last row read

    with open(csv_path, 'w', newline='\n') as out:
        out.write(HEADER)
        for name, lon, lat, alt, omega, phi, kappa in rows:
            out.write(','.join([name + '.jpg', lon, lat, alt, omega, phi, kappa, '0.1', '0.3']) + '\n')
    return len(rows), expected


def main():
    if len(sys.argv) > 1:
        eo_path = sys.argv[1]
    else:
        from tkinter import Tk
        from tkinter.filedialog import askopenfilename
        Tk().withdraw()
        eo_path = askopenfilename(initialdir=r"E:\GPS\PosPac-Projects", title="Select EO file",
                                  filetypes=[("TXT files", "*.txt")])
        if not eo_path:
            print("No file selected")
            return

    if len(sys.argv) > 2:
        csv_path = sys.argv[2]
    else:
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join(os.path.dirname(eo_path), stamp + '_gps-imu-data.csv')

    print(eo_path)
    count, last_event = convert(eo_path, csv_path)
    print("File Created:", csv_path)
    print("Rows written:", count)
    if count == 0:
        print("WARNING: no data rows found - is this a POSPac EO file?")
    elif last_event != count:
        print("WARNING: last EVENT number in the EO file is %d but %d rows were written - check for skipped rows" % (last_event, count))


if __name__ == '__main__':
    main()
