#! /usr/bin/python3

# External deps
import sys, os
import matplotlib.pyplot as plt

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
from df_common import JSON_ARC, JSON_CMP_STR, JSON_CMP_CNT, JSON_PRI_CMP_CNT, JSON_LNE_CNT, GEN_FILE_DIR
import analyses_common as ac

if os.path.exists(os.path.join(GEN_FILE_DIR, "sloc_cnt.py")):
    sys.path.append(GEN_FILE_DIR)
    from sloc_cnt import DRIVER_NAME_TO_SLOC
else:
    print("Error: no SLOC file! Run \'df_analyze.py\' with \'--linux-src-dir\'")
    sys.exit(1)

def get_sloc_list_by_arch(cmp_by_arch, sloc_cnts, verbose = False):

    '''
    For each architecture:
        1) For every cmp str present in DTBs of that arch, see if we know SLOC from the source code
        2) If there are multiple source files for that cmp str, use the average
        3) Build a dict in the form of {arch: [sloc_drvr_1, sloc_drvr_2, sloc_drvr_3, ... ]}
    '''

    sloc_list_by_arch = {}

    for arch in cmp_by_arch:

        # Some cmp strs (ex. `simple-bus`) have multiple drivers
        # We don't want to double count these, instead computer a running average
        # Important to clear this every arch, so that each arch uses only data from it's DTBs
        cmp_str_to_slocs = {}

        # List of all compatible stings for given arch
        cmps_strs_for_arch = list(cmp_by_arch[arch].keys())

        # For every compatible sting, check if we have SLOC count from the parsing the source code
        # If multiple drivers are defined for this cmp str, log SLOC for each so we can compute average later
        for cmp_str_dtb in cmps_strs_for_arch:
            for tup in sloc_cnts.keys():
                for cmp_str_src in tup:
                    if (cmp_str_src == cmp_str_dtb):
                        if cmp_str_dtb not in cmp_str_to_slocs:
                            cmp_str_to_slocs[cmp_str_dtb] = [sloc_cnts[tup]]
                        else:
                            cmp_str_to_slocs[cmp_str_dtb].append(sloc_cnts[tup])

        # Now that we have SLOC counts for all cmp strs, create a list of their averages to represent the architecture
        for cmp_str in cmp_str_to_slocs:

            avg_sloc = sum(cmp_str_to_slocs[cmp_str]) / len(cmp_str_to_slocs[cmp_str])

            # List of SLOC values for drivers of a given arch
            if arch not in sloc_list_by_arch:
                sloc_list_by_arch[arch] = [avg_sloc]
            else:
                sloc_list_by_arch[arch].append(avg_sloc)

            if verbose:
                print("Average SLOC for \'{}\' ({}): {}".format(
                    cmp_str, arch, avg_sloc))

    return sloc_list_by_arch

def get_sloc_avg_and_list_by_arch(cmp_by_arch, verbose = True):

    '''
    Architecture-specific SLOC averages
    '''

    sloc_list_by_arch =  get_sloc_list_by_arch(cmp_by_arch, DRIVER_NAME_TO_SLOC, verbose)

    avg_sloc_by_arch = {}
    for arch in cmp_by_arch:
        average_sloc, _, _ = ac.get_mean_median_std_dev(sloc_list_by_arch[arch])
        avg_sloc_by_arch[arch] = average_sloc

    return avg_sloc_by_arch, sloc_list_by_arch


if __name__ == "__main__":

    # Collection
    json_files = ac.argparse_and_get_files("Graph stats on driver SLOC")
    dtb_cnt = len(json_files)

    cmp_by_arch = ac.build_dict_two_lvl_cnt(json_files, JSON_ARC, JSON_CMP_STR)
    dtb_cnt_by_arch = ac.build_dict_one_lvl_cnt(json_files, JSON_ARC)
    pri_cmp_cnt_by_arch = ac.build_dict_one_lvl_sum(json_files, JSON_ARC, JSON_PRI_CMP_CNT)
    avg_sloc_by_arch, sloc_list_by_arch = get_sloc_avg_and_list_by_arch(cmp_by_arch)

    open_drivers_all = [cmp_str for tup in DRIVER_NAME_TO_SLOC.keys() for cmp_str in tup] # Flatten tuples keys into a list
    ac.print_mean_median_std_dev_for_dict_of_lists(sloc_list_by_arch,
        "\nSloc Per Driver, format: [arch : (mean, median, std_dev)]\n")

    # Build graph 1 - count of open-source drivers by architecture
    ac.graph_simple_bar(
        [arch for arch in cmp_by_arch],
        [len([cmp_str for cmp_str in cmp_by_arch[arch] if cmp_str in open_drivers_all]) for arch in cmp_by_arch],
        'Architectures',
        'Count of Open-source Peripheral Drivers',
        'Count of Open-source Peripheral Drivers By Architecture ({} DTBs)'.format(dtb_cnt),
        'blue'
    )

    # Build graph 2 - percentage of open-source drivers by architecture
    ac.graph_simple_bar(
        [arch for arch in cmp_by_arch],
        [(len([cmp_str for cmp_str in cmp_by_arch[arch] if cmp_str in open_drivers_all]) /
            len([cmp_str for cmp_str in cmp_by_arch[arch]]))
            for arch in cmp_by_arch],
        'Architectures',
        'Percentage of Open-source Peripheral Drivers',
        'Percentage of Open-source Peripheral Drivers By Architecture ({} DTBs)'.format(dtb_cnt),
        'orange'
    )

    # Build graph 3 - Average SLOC per open driver by arch
    ac.graph_simple_bar(
        [arch for arch in cmp_by_arch],
        [avg_sloc_by_arch[arch] for arch in cmp_by_arch],
        'Architectures',
        'Average SLOC per Open-source Peripheral Driver',
        'Average SLOC per Open-source Peripheral Driver By Architecture ({} DTBs)'.format(dtb_cnt),
        'red'
    )

    '''
    # Don't use this - it over estimates!
    # Build graph 4 - Estimated Driver SLOC per SoC
    ac.graph_simple_bar(
        [arch for arch in cmp_by_arch],
        # (Avg SLOC per peripheral driver) * (Avg named peripherals per SoC)
        [avg_sloc_by_arch[arch] * (pri_cmp_cnt_by_arch[arch] / dtb_cnt_by_arch[arch]) for arch in cmp_by_arch],
        'Architectures',
        'Estimated Driver SLOC per SoC',
        'Estimated Driver SLOC per SoC By Architecture ({} DTBs)'.format(dtb_cnt),
        'green'
    )
    '''

    # Display graphs
    plt.show()