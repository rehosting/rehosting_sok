#! /usr/bin/python3

# External deps
import sys, os, operator
import matplotlib.pyplot as plt

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
from df_common import JSON_ARC, JSON_CMP_STR, JSON_PRI_CMP_STR, JSON_CMP_CNT, JSON_PRI_CMP_CNT
import analyses_common as ac

if __name__ == "__main__":

    # True == consider only the first-choice compatible string for a node
    # False == consider all compatible strings for a node, and model string if compatible isn't present
    PRIMARY_CMP_STR_ONLY = True

    # Collection
    json_files = ac.argparse_and_get_files("Graph stats on compatible/model strings")
    dtb_cnt = len(json_files)
    dtb_cnt_by_arch = ac.build_dict_one_lvl_cnt(json_files, JSON_ARC)

    if PRIMARY_CMP_STR_ONLY:
        cmp_by_arch = ac.build_dict_two_lvl_cnt(json_files, JSON_ARC, JSON_PRI_CMP_STR)
        cmp_cnt_by_arch = ac.build_dict_one_lvl_sum(json_files, JSON_ARC, JSON_PRI_CMP_CNT)
        list_peripheral_cnt_by_arch = ac.build_dict_one_lvl_list(json_files, JSON_ARC, JSON_PRI_CMP_CNT)
    else:
        cmp_by_arch = ac.build_dict_two_lvl_cnt(json_files, JSON_ARC, JSON_CMP_STR)
        cmp_cnt_by_arch = ac.build_dict_one_lvl_sum(json_files, JSON_ARC, JSON_CMP_CNT)
        list_peripheral_cnt_by_arch = ac.build_dict_one_lvl_list(json_files, JSON_ARC, JSON_CMP_CNT)

    ac.print_mean_median_std_dev_for_dict_of_lists(list_peripheral_cnt_by_arch,
        "\nPeripheral count per SoC, format: [arch : (mean, median, std_dev)]\n")

    print("\nTotal unique peripherals by architecture:")
    total_p_cnt = 0
    for arch in cmp_by_arch:
        arch_p_cnt = len([cmp_str for cmp_str in cmp_by_arch[arch]])
        print(f"{arch}: {arch_p_cnt}")
        total_p_cnt += arch_p_cnt

    print(f"\nTotal unique peripherals: {total_p_cnt}")

    # Build graph 1 - unique peripherals by architecture
    ac.graph_simple_bar(
        [arch for arch in cmp_by_arch],
        [len([cmp_str for cmp_str in cmp_by_arch[arch]]) for arch in cmp_by_arch],
        'Architectures',
        'Count of Unique Peripheral Names',
        'Peripheral Diversity By Architecture ({} DTBs)'.format(dtb_cnt),
        'blue'
    )

    # Build graph 2 - average peripherals per DTB by architecture
    ac.graph_simple_bar(
        [arch for arch in cmp_cnt_by_arch],
        [(cmp_cnt_by_arch[arch] / dtb_cnt_by_arch[arch]) for arch in cmp_cnt_by_arch],
        'Architectures',
        'Average Unique Peripheral Names Per DTB',
        'Average Peripheral Count By Architecture ({} DTBs)'.format(dtb_cnt),
        'orange'
    )

    # Build graph 3 - top 10 peripherals by architecture
    ac.graph_multibar_top_n_items(
        10,
        cmp_by_arch,
        'Ranking 1-10',
        'Count of DTBs Peripheral Present In',
        'Top 10 Peripherals by Architecture ({} DTBs)'.format(dtb_cnt),
    )

    '''
    # Top 10 print
    for arch in cmp_by_arch:
        sorted_cmp_strs = sorted(cmp_by_arch[arch].items(), key=operator.itemgetter(1), reverse=True)
        print("\nTop 10 cmp_strs ({}):".format(arch))
        for i in range(0, 10):
            print(sorted_cmp_strs[i])
    '''

    # Display graphs
    plt.show()