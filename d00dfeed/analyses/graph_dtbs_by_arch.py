#! /usr/bin/python3

# External deps
import sys, os
import matplotlib.pyplot as plt

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
from df_common import JSON_ARC
import analyses_common as ac

if __name__ == "__main__":

    # Collection
    json_files = ac.argparse_and_get_files("Graph count of DTBs by architecture")
    dtb_cnt_by_arch = ac.build_dict_one_lvl_cnt(json_files, JSON_ARC)
    dtb_cnt = len(json_files)

    print("\nTotal DTBs by architecture:")
    for arch in dtb_cnt_by_arch:
        print(f"{arch}: {dtb_cnt_by_arch[arch]}")

    # Graph
    ac.graph_simple_bar(
        [arch for arch in dtb_cnt_by_arch],
        [dtb_cnt_by_arch[arch] for arch in dtb_cnt_by_arch],
        'Architectures',
        'Count of DTBs',
        'Count of DTBs by Architecture ({} total DTBs)'.format(dtb_cnt),
        'green'
    )
    plt.show()