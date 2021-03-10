# External deps
import os, sys, json
from pathlib import Path
from typing import Dict, List

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
import df_common as dfc
import analyses_common as ac

# Generated files directory
GEN_FILE_DIR = str(Path(__file__).resolve().parent.parent) + os.sep + "generated_files" # TODO: ugly parent.parent pathing
if os.path.exists(GEN_FILE_DIR):
    sys.path.append(GEN_FILE_DIR)
    if os.path.exists(os.path.join(GEN_FILE_DIR, "sloc_cnt.py")):
        from sloc_cnt import DRIVER_NAME_TO_SLOC
else:
    print("Error: no SLOC file! Run \'df_analyze.py\' with \'--linux-src-dir\'")
    sys.exit(1)

if __name__ == "__main__":

    json_files = ac.argparse_and_get_files("Graph SLOC/SoC data")
    soc_sloc_by_arch: Dict[str, List[int]] = {}

    print("Gathering SLOC average by arch...")
    from graph_dd_sloc_by_arch import get_sloc_avg_and_list_by_arch
    cmp_by_arch = ac.build_dict_two_lvl_cnt(json_files, dfc.JSON_ARC, dfc.JSON_CMP_STR)
    avg_sloc_by_arch, sloc_list_by_arch = get_sloc_avg_and_list_by_arch(cmp_by_arch, verbose = False)

    # Collection
    print("Iterating DTBs/SoCs...")
    for dtb_json in json_files:

        with open(dtb_json) as json_file:
            data = json.load(json_file)

        soc_sloc = 0
        arch = data[dfc.JSON_ARC]
        cmp_strs = data[dfc.JSON_CMP_STR]

        # Total SLOC for this SoC
        for cmp_str in cmp_strs:
            driver_sloc = dfc.cmp_str_to_sloc(cmp_str)
            if not driver_sloc: # Closed-source driver
                driver_sloc = avg_sloc_by_arch[arch]
            soc_sloc += driver_sloc
            #print("{}: {}".format(cmp_str, driver_sloc))

        if arch not in soc_sloc_by_arch:
            soc_sloc_by_arch[arch] = []
        else:
            soc_sloc_by_arch[arch].append(soc_sloc)

        print("{} ({}): {}".format(dtb_json.split(os.sep)[-1], arch, soc_sloc))

    # Final stats
    ac.print_mean_median_std_dev_for_dict_of_lists(soc_sloc_by_arch,
        "\nSloc Per Soc, format: [arch : (mean, median, std_dev)]\n")


