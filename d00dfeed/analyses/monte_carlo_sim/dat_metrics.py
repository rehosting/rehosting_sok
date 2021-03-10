#! /usr/bin/python3

import statistics as stats

def get_last_data(f):
    return ([line.strip() for line in f.readlines()][-1]).split(" ")

# Means SLOC per simulation
with open("monte_sloc_all_sims.dat") as f:
    sloc_totals = [float(line.strip()) for line in f.readlines()]
    print("Mean SLOC: {}".format(stats.mean(sloc_totals)))

# Mean unimplemented peripherals for final DTB rehost attempt
with open("monte_unimp_per_rehost.dat") as f:
    final_rehost = [int(num) for num in get_last_data(f)]
    del final_rehost[0]
    print("Mean P_u len at final rehost: {}".format(stats.mean(final_rehost)))

# Mean total peripherals for final DTB rehost attempt
with open("monte_totals_per_rehost.dat") as f:
    final_rehost = [int(num) for num in get_last_data(f)]
    del final_rehost[0]
    print("Mean P_m len at final rehost: {}".format(stats.mean(final_rehost)))

