#! /usr/bin/python3

# External deps
import sys, os
import matplotlib.pyplot as plt

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
from df_common import JSON_ARC, JSON_CMP_STR, JSON_CMP_CNT, JSON_PRI_CMP_CNT, JSON_LNE_CNT, GEN_FILE_DIR
import analyses_common as ac

if os.path.exists(os.path.join(GEN_FILE_DIR, "driver_types.py")):
    sys.path.append(GEN_FILE_DIR)
    from driver_types import DRIVER_NAME_TO_TYPE
else:
    print("Error: no driver types file! Run \'df_analyze.py\' with \'--linux-src-dir\'")
    sys.exit(1)

def get_type(cmp_str_in):

    '''
    Lookup type for a given compatible string
    '''

    for cmp_strs, type_str in DRIVER_NAME_TO_TYPE.items():
        for cmp_str in cmp_strs:
            if cmp_str == cmp_str_in:
                return type_str

    return None

def bin_by_type(cmp_str_to_cnt_dict, verbose=False):

    '''
    Bin peripherals discovered into functional categories
    '''

    type_to_raw_cnt = {}
    type_to_unique_cnt = {}
    type_to_dominant_cnt = {}

    for cmp_str, cmp_str_cnt in cmp_str_to_cnt_dict.items():

        # Only consider cmp strs we have source for!
        periph_type = get_type(cmp_str)
        if periph_type:

            if verbose:
                print("{}({}) -> {}".format(cmp_str, cmp_str_cnt, periph_type))

            # Create dict entries
            if periph_type not in type_to_raw_cnt:
                type_to_raw_cnt[periph_type] = cmp_str_cnt
                type_to_unique_cnt[periph_type] = 1
                type_to_dominant_cnt[periph_type] = cmp_str_cnt

            # Update dict entires
            else:
                type_to_raw_cnt[periph_type] += cmp_str_cnt
                type_to_unique_cnt[periph_type] += 1
                if (type_to_dominant_cnt[periph_type] < cmp_str_cnt):
                    type_to_dominant_cnt[periph_type] = cmp_str_cnt

    return type_to_raw_cnt, type_to_unique_cnt, type_to_dominant_cnt

if __name__ == "__main__":

    json_files = ac.argparse_and_get_files("Print device type info.")
    dtb_cnt = len(json_files)

    cmp_by_arch = ac.build_dict_two_lvl_cnt(json_files, JSON_ARC, JSON_CMP_STR)
    for arch in cmp_by_arch:

        print("\nProcessing {}...".format(arch))
        type_to_raw_cnt, type_to_unique_cnt, type_to_dominant_cnt = bin_by_type(cmp_by_arch[arch], verbose=True)

        type_to_dominant_percentage = {}
        for periph_type, dom_cnt in type_to_dominant_cnt.items():
            type_to_dominant_percentage[periph_type] = (dom_cnt / type_to_raw_cnt[periph_type])

        output = {}
        for periph_type in type_to_raw_cnt:
            output[periph_type] = [
                type_to_unique_cnt[periph_type],
                type_to_raw_cnt[periph_type],
                type_to_dominant_percentage[periph_type],
            ]

        print("\n\t{}".format(arch.upper()))
        for periph_type, res in sorted(output.items(), key=lambda l: l[1][0], reverse=True):
            print("\t{}: {}".format(periph_type, res))

        #print("\n{} UNIQUE COUNTS".format(arch.upper()))
        #print(type_to_unique_cnt)
        #print("\n{} RAW COUNTS".format(arch.upper()))
        #print(type_to_raw_cnt)
        #print("\n{} DOMINANT PERCENTAGES".format(arch.upper()))
        #print(type_to_dominant_percentage)

