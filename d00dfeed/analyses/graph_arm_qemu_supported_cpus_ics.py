#! /usr/bin/python3

# External deps
import sys, os
import matplotlib.pyplot as plt

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
import df_common as dfc
import analyses_common as ac

# Global Consts
CPU_FUZ_THRES = 100
INT_FUZ_THRES = 90
generic_arm_cpu_names = ['armv8', 'armv7']

if __name__ == "__main__":

    # Collection
    json_files = ac.argparse_and_get_files("Graph percentage of QEMU supported CPUs and ICs for ARM and ARM64")
    dtb_cnt_by_arch = ac.build_dict_one_lvl_cnt(json_files, dfc.JSON_ARC)
    cpu_by_arch = ac.build_dict_two_lvl_cnt(json_files, dfc.JSON_ARC, dfc.JSON_CPU)
    int_by_arch = ac.build_dict_two_lvl_cnt(json_files, dfc.JSON_ARC, dfc.JSON_INT)
    qemu_arm_cpus = dfc.get_all_qemu_strs_by_arch('arm', get_cpus=True, get_devs=False)
    qemu_arm_devs = dfc.get_all_qemu_strs_by_arch('arm', get_cpus=False, get_devs=True)
    qemu_arm64_cpus = dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=True, get_devs=False)
    qemu_arm64_devs = dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=False, get_devs=True)

    # Manual adjustment:
    # Some DTBs use generic specification for the CPU, ex "arm,armv8" - this likely means any CPU that supports the
    # specified ISA version will work. Need to count that as supported.
    qemu_arm_cpus.extend(generic_arm_cpu_names)
    qemu_arm64_cpus.extend(generic_arm_cpu_names)

    # Filtering
    arm_cpus = [dfc.strip_vendor_prefix(x) for x in cpu_by_arch['arm']]
    arm_ints = [dfc.strip_vendor_prefix(x) for x in int_by_arch['arm']]
    arm64_cpus = [dfc.strip_vendor_prefix(x) for x in cpu_by_arch['arm64']]
    arm64_ints = [dfc.strip_vendor_prefix(x) for x in int_by_arch['arm64']]

    # Fuzzy matching
    cnt_qemu_supported_arm_cpus = len(dfc.get_fuzzy_matches(arm_cpus, qemu_arm_cpus, threshold=CPU_FUZ_THRES, verbose=True))
    cnt_qemu_supported_arm_ints = len(dfc.get_fuzzy_matches(arm_ints, qemu_arm_devs, threshold=INT_FUZ_THRES, verbose=True))
    cnt_qemu_supported_arm64_cpus = len(dfc.get_fuzzy_matches(arm64_cpus, qemu_arm64_cpus, threshold=CPU_FUZ_THRES, verbose=True))
    cnt_qemu_supported_arm64_ints = len(dfc.get_fuzzy_matches(arm64_ints, qemu_arm64_devs, threshold=INT_FUZ_THRES, verbose=True))

    # Data
    total_dtbs = (dtb_cnt_by_arch['arm'] + dtb_cnt_by_arch['arm64'])

    x = [
        'arm_CPUs',
        'arm_ICs',
        'arm64_CPUs',
        'arm64_ICs'
    ]

    y = [
        (cnt_qemu_supported_arm_cpus / len(arm_cpus)),
        (cnt_qemu_supported_arm_ints / len(arm_ints)),
        (cnt_qemu_supported_arm64_cpus / len(arm64_cpus)),
        (cnt_qemu_supported_arm64_ints / len(arm64_ints)),
    ]

    # Graph
    ac.graph_simple_bar(
        x,
        y,
        'Label format: <Architecture>_<Category>',
        'Percentage Supported In QEMU',
        'Percentage of QEMU Supported CPUs and Interrupt Controllers ({} total DTBs)'.format(total_dtbs),
        'purple'
    )
    plt.show()
