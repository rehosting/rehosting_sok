#! /usr/bin/python3

# External deps
import os, sys

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
import df_common as dfc

########################################################################################################################
# HELPERS
########################################################################################################################

def print_qemu_peripheral_counts():

    arm_p_cnt = len(dfc.get_all_qemu_strs_by_arch('arm', get_cpus=False, get_devs=True))
    arm64_p_cnt = len(dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=False, get_devs=True))
    mips_p_cnt = len(dfc.get_all_qemu_strs_by_arch('mips', get_cpus=False, get_devs=True))
    ppc_p_cnt = len(dfc.get_all_qemu_strs_by_arch('ppc', get_cpus=False, get_devs=True))

    print("ARM: {}".format(arm_p_cnt))
    print("ARM64: {}".format(arm64_p_cnt))
    print("MIPS: {}".format(mips_p_cnt))
    print("PPC: {}".format(ppc_p_cnt))

    print("Total: {}".format(arm_p_cnt + arm64_p_cnt + mips_p_cnt + ppc_p_cnt))

if __name__ == "__main__":
    print_qemu_peripheral_counts()
