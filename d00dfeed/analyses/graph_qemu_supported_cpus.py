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
generic_arm_cpu_names = ['armv8', 'armv7']

if __name__ == "__main__":

    # Collection
    json_files = ac.argparse_and_get_files("Graph percentage of QEMU supported CPUs and ICs for ARM and ARM64")
    dtb_cnt_by_arch = ac.build_dict_one_lvl_cnt(json_files, dfc.JSON_ARC)
    cpu_by_arch = ac.build_dict_two_lvl_cnt(json_files, dfc.JSON_ARC, dfc.JSON_CPU)
    qemu_arm_cpus = dfc.get_all_qemu_strs_by_arch('arm', get_cpus=True, get_devs=False)
    print(f"\nARM CPUs: {qemu_arm_cpus}")
    qemu_arm64_cpus = dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=True, get_devs=False)
    print(f"\nARM64 CPUs: {qemu_arm64_cpus}")
    qemu_mips_cpus = dfc.get_all_qemu_strs_by_arch('mips', get_cpus=True, get_devs=False)
    print(f"\nMIPS CPUs: {qemu_mips_cpus}")
    qemu_ppc_cpus = dfc.get_all_qemu_strs_by_arch('ppc', get_cpus=True, get_devs=False)
    print(f"\nPPC CPUs: {qemu_ppc_cpus}")

    # Manual adjustment:
    # Some DTBs use generic specification for the CPU, ex "arm,armv8" - this likely means any CPU that supports the
    # specified ISA version will work. Need to count that as supported.
    qemu_arm_cpus.extend(generic_arm_cpu_names)
    qemu_arm64_cpus.extend(generic_arm_cpu_names)

    # Filtering
    arm_cpus = [dfc.strip_vendor_prefix(x) for x in cpu_by_arch['arm']]
    arm64_cpus = [dfc.strip_vendor_prefix(x) for x in cpu_by_arch['arm64']]
    mips_cpus = [dfc.strip_vendor_prefix(x) for x in cpu_by_arch['mips']]
    ppc_cpus = [dfc.strip_vendor_prefix(x) for x in cpu_by_arch['powerpc']]

    # Fuzzy matching
    cnt_qemu_supported_arm_cpus = len(dfc.get_fuzzy_matches(arm_cpus, qemu_arm_cpus, threshold=98, verbose=True))
    cnt_qemu_supported_arm64_cpus = len(dfc.get_fuzzy_matches(arm64_cpus, qemu_arm64_cpus, threshold=98, verbose=True))
    cnt_qemu_supported_mips_cpus = len(dfc.get_fuzzy_matches(mips_cpus, qemu_mips_cpus, threshold=90, verbose=True))
    cnt_qemu_supported_ppc_cpus = len(dfc.get_fuzzy_matches(ppc_cpus, qemu_ppc_cpus, threshold=90, verbose=True))

    # Percent supported
    arm_support = (cnt_qemu_supported_arm_cpus / len(arm_cpus))
    arm64_support = (cnt_qemu_supported_arm64_cpus / len(arm64_cpus))
    mips_support = (cnt_qemu_supported_mips_cpus / len(mips_cpus))
    ppc_support = (cnt_qemu_supported_ppc_cpus / len(ppc_cpus))

    # Debug print
    print("\n")
    print(f"ARM - CPU Models Available: {len(qemu_arm_cpus)}, supported: {arm_support * 100}%")
    print(f"ARM64 - CPU Models Available: {len(qemu_arm64_cpus)},  supported: {arm64_support * 100}%")
    print(f"MIPS - CPU Models Available: {len(qemu_mips_cpus)}, supported: {mips_support * 100}%")
    print(f"PPC - CPU Models Available: {len(qemu_ppc_cpus)}, supported: {ppc_support * 100}%")

    # Data
    total_dtbs = (
                    dtb_cnt_by_arch['arm']
                    + dtb_cnt_by_arch['arm64']
                    + dtb_cnt_by_arch['mips']
                    + dtb_cnt_by_arch['powerpc']
                )

    x = [
        'arm_CPUs',
        'arm64_CPUs',
        'mips_CPUs',
        'ppc_CPUs',
    ]

    y = [
        arm_support,
        arm64_support,
        mips_support,
        ppc_support
    ]

    # Graph
    ac.graph_simple_bar(
        x,
        y,
        'Label format: <Architecture>_<Category>',
        'Percentage Supported In QEMU',
        'Percentage of QEMU Supported CPUs ({} total DTBs)'.format(total_dtbs),
        'green'
    )
    plt.show()
