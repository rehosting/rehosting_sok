#!/usr/bin/env python3

import os
import pickle
import statistics
from cmsis_svd.parser import SVDParser
from pathlib import Path

# For each SVD file, examine each peripheral
# Determine if a peripheral was already seen

cache_file = "periphc_by_family.pickle"
if os.path.isfile(cache_file):
    with open(cache_file, "rb") as f:
        periph_count = pickle.load(f)
else:
    periph_count = {}
    svd_files = Path("../cmsis-svd/data/").glob("**/*.svd")
    for f in svd_files:
        vendor = f.parts[-2]
        parser = SVDParser.for_xml_file(f)
        try:
            device = parser.get_device()
        except (TypeError, KeyError):
            # cmsis-svd can't parse all the files in its corpus
            print(f"Error parsing SVD file {f} - skipping")
            continue

        if vendor not in periph_count:
            periph_count[vendor] = []

        periph_count[vendor].append(len(device.peripherals)) # TODO: only count distinct peripherals within that family

    with open(cache_file, "wb") as f:
        pickle.dump(periph_count, f)

total_p_count = sum([sum(x) for x in periph_count.values()]) # Across all families
total_n_systems = sum([len(x) for x in periph_count.values()])
avg_periph = total_p_count/total_n_systems

print(f"Across {total_n_systems} devices, a total of {total_p_count} peripherals " +
        f"(including duplicates are described). On average, each system has {avg_periph:.02f} peripherals")

for vendor in sorted(periph_count, key=lambda k: len(periph_count[k]), reverse=True):
    this_count = periph_count[vendor]
    if len(this_count) < 5:
        continue
    mn = statistics.mean(this_count)
    med = statistics.median(this_count)
    stdev = statistics.stdev(this_count)


    print(f"{vendor: >20}: n={len(this_count): >3}, PeriphC(dup) = {sum(this_count): >3}, mean: {mn:.02f} +- {stdev:.02f}, median: {med}")

"""
Across 640 devices, a total of 32774 peripherals (including duplicates are described). On average, each system has 51.21 peripherals
Atmel: n=147, PeriphC(dup) = 5635, mean: 38.33 +- 12.21, median: 34
Freescale: n=133, PeriphC(dup) = 7834, mean: 58.90 +- 14.21, median: 57
Fujitsu: n=100, PeriphC(dup) = 4695, mean: 46.95 +- 11.05, median: 43.0
Spansion: n= 88, PeriphC(dup) = 4233, mean: 48.10 +- 12.23, median: 43.0
STMicro: n= 72, PeriphC(dup) = 5338, mean: 74.14 +- 30.39, median: 70.5
TexasInstruments: n= 52, PeriphC(dup) = 3051, mean: 58.67 +- 6.43, median: 57.5
NXP: n= 24, PeriphC(dup) = 847, mean: 35.29 +- 22.36, median: 31.5
SiliconLabs: n= 10, PeriphC(dup) = 499, mean: 49.90 +- 3.00, median: 51.5
Toshiba: n=  6, PeriphC(dup) = 358, mean: 59.67 +- 26.39, median: 52.0
"""
