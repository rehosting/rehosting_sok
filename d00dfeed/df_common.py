#! /usr/bin/python3

import os, subprocess, logging, sys
from collections import namedtuple
from itertools import zip_longest, chain
from fuzzywuzzy import process as fzy_proc
import statistics as stats
from pathlib import Path

# Generated files directory
GEN_FILE_DIR = str(Path(__file__).resolve().parent) + os.sep + "generated_files"
if os.path.exists(GEN_FILE_DIR):
    sys.path.append(GEN_FILE_DIR)
if os.path.exists(os.path.join(GEN_FILE_DIR, "arch_signatures.py")):
    from arch_signatures import UNIQUE_DEVS_BY_ARCH
if os.path.exists(os.path.join(GEN_FILE_DIR, "sloc_cnt.py")):
    from sloc_cnt import DRIVER_NAME_TO_SLOC

########################################################################################################################
# GLOBALS
########################################################################################################################

STR_ENCODING = 'utf-8'

# Generally useful property strings (for DTB)
MEM_STR = "memory"
MOD_STR = "model"
CMP_STR = "compatible"
REG_STR = "reg"
RNG_STR = "ranges"
CPU_STR = "cpus"
BTA_STR = "bootargs"
CHO_STR = "chosen"
STA_STR = "status"
NAC_STR = "#address-cells"
NSC_STR = "#size-cells"
DEV_STR = "device_type"

# Property strings unique to a device class (for class inference, for DTB)

CPU_PROPS = [
	'd-cache-size',
	'd-cache-sets',
	'd-cache-block-size',
	'd-cache-line-size',
    'd-cache-baseaddr',
	'd-cache-highaddr',
    'i-cache-size',
	'i-cache-sets',
	'i-cache-block-size',
	'i-cache-line-size',
	'i-cache-baseaddr',
	'i-cache-highaddr',
    'cpu-release-addr',
    'power-isa-version',
    'mmu-type',
    'tlb-split',
    'tlb-size',
    'tlb-sets',
    'd-tlb-size',
    'd-tlb-sets',
    'i-tlb-size',
    'i-tlb-sets',
]

INT_PROPS = [
    'interrupt-controller',
]

NET_PROPS = [
    'address-bits',
    'local-mac-address',
    'mac-address',
    'max-frame-size',
]

ETH_PROPS = [
    'max-speed',
    'phy-connection-type',
]

# JSON labels (for our scripts, not DTB)
JSON_CPU = 'cpu'
JSON_INT = 'int_ctrl'
JSON_ARC = 'arch'
JSON_CMP_CNT = 'cmp_str_cnt'
JSON_CMP_STR = 'cmp_strs'
JSON_PRI_CMP_CNT = 'primary_cmp_str_cnt'
JSON_PRI_CMP_STR = 'primary_cmp_strs'
JSON_MIO_CNT = 'mmio_node_cnt'
JSON_LNE_CNT = 'line_cnt'

# Named tuples
Dev_mem_map = namedtuple('Dev_mem_map', 'addr size')
Dev_prop_vals = namedtuple('Dev_prop_vals', 'node val')
Containing_full_path_tuple = namedtuple('Containing_full_path_tuple', 'containing_path full_path')

# Misc
NUM_WIDTH = 32
USE_SYS_QEMU = True

# QEMU default binary/machine mappings
if USE_SYS_QEMU:
    ARCH_TO_QEMU_BIN = {
        "arm" : "qemu-system-arm",
        "arm64" : "qemu-system-aarch64",
        "microblaze" : "qemu-system-microblaze",
        "mips" : "qemu-system-mips",
        "ppc" : "qemu-system-ppc"
    }
else:
    # Note - you should never need this if using the container
    ARCH_TO_QEMU_BIN = {
        "arm" : str(Path.home().joinpath("Downloads", "qemu-5.2.0", "build", "arm-softmmu", "qemu-system-arm")),
        "arm64" : str(Path.home().joinpath("Downloads", "qemu-5.2.0","build", "aarch64-softmmu", "qemu-system-aarch64")),
        "microblaze" : str(Path.home().joinpath("Downloads", "qemu-5.2.0","build", "microblaze-softmmu", "qemu-system-microblaze")),
        "mips" : str(Path.home().joinpath("Downloads", "qemu-5.2.0","build", "mips-softmmu", "qemu-system-mips")),
        "ppc" : str(Path.home().joinpath("Downloads", "qemu-5.2.0","build", "ppc-softmmu", "qemu-system-ppc"))
    }

########################################################################################################################
# PERIPHERAL STATISTICS
########################################################################################################################

def get_mmio_nodes(dtb_obj):

    '''
    Get nodes for MMIO devices for the DTB
    Note: per DTB-spec reg property may have a different meaning on some bus types (slight overapproximation)
    '''

    return dtb_obj.get_devs_by_prop(REG_STR)

def get_cmp_nodes(dtb_obj, mod_str=False):

    '''
    Get a list of nodes containing named device strings (compatible string, or, optionally model if compatible
    isn't present). Getting node-level info is useful for equivlance classes (ex. 3 compatible strings for same node)
    '''

    devs = []
    devs_with_cmp = dtb_obj.get_devs_by_prop(CMP_STR)

    # Model strings if compatible string isn't available
    if mod_str:

        devs_with_mod = dtb_obj.get_devs_by_prop(MOD_STR)

        # Don't double count devices with both "compatible" and "model", compatible takes precedence
        # Can't just use set() b/c we have (dev_node, prop_data) tuples - the latter will differ
        for dev_mod in devs_with_mod:
            if dev_mod.node in [dev_cmp.node for dev_cmp in devs_with_cmp]:
                devs_with_mod.remove(dev_mod)

        devs = devs_with_cmp + devs_with_mod

    # Only compatible strings
    else:
        devs = devs_with_cmp

    return devs

def get_cmp_strs(dtb_obj, primary_only=False):

    '''
    Get a list of named device strings. Intended as a proxy for device diversity.
    Note compatible strings are precedence-ordered.
    '''

    strs = []

    # Only primary (first choice) compatible strings
    if primary_only:
        devs = get_cmp_nodes(dtb_obj, mod_str=False)
        for dev in devs:
            strs.append(dev.val[0])

    # All compatible strings and any model strings if compatible isn't available
    else:
        devs = get_cmp_nodes(dtb_obj, mod_str=True)
        for dev in devs:
            strs.extend(dev.val)

    return list(set(strs))

def get_cpu(dtb_obj):

    '''
    Determine CPU model string(s) for the input DTB
    '''

    cpu_strs = set()
    cpu_nodes = []
    generic_names = ['cpus', 'cpu', 'cpu-map', 'cache', 'arm,idle-state', 'idle-states']

    # Case 1 - nodes with [device_type = "cpu"]
    nodes = dtb_obj.get_nodes_by_prop(DEV_STR)
    for node in nodes:
        if (node.get_property(DEV_STR)[0] == "cpu"):
            cpu_nodes.append(node)

    # Case 2 - nodes containing a CPU-specific property
    for prop in CPU_PROPS:
        nodes = dtb_obj.get_nodes_by_prop(prop)
        for node in nodes:
            if node not in cpu_nodes:
                cpu_nodes.append(node)

    # Case 3 - Children of the "cpus" node
    top_level_cpus_node = dtb_obj.get_node_by_name("cpus")
    if top_level_cpus_node:
        for node in top_level_cpus_node.nodes:
            if node not in cpu_nodes:
                cpu_nodes.append(node)

    # Get CPU names
    for node in cpu_nodes:
        if node.exist_property(CMP_STR):
            for name_str in node.get_property(CMP_STR):
                if name_str not in generic_names:
                    cpu_strs.add(name_str)
        else:
            if node.name not in generic_names:
                name_str = node.name.split("@")[0]
                if name_str not in generic_names:
                    cpu_strs.add(name_str)

    # Use "Unknown" if no names could be determined
    if (len(cpu_strs) == 0):
        cpu_strs.add("Unknown")

    return list(cpu_strs)

def get_int(dtb_obj):

    '''
    Determine Interrupt Controller model string(s) for the input DTB
    '''

    ic_strs = set()
    ic_nodes = []
    generic_names = ['simple-bus']

    # Case 1 - nodes containing a IC-specific property
    for prop in INT_PROPS:
        nodes = dtb_obj.get_nodes_by_prop(prop)
        for node in nodes:
            if node not in ic_nodes:
                ic_nodes.append(node)

    # Get IC names
    for node in ic_nodes:
        if node.exist_property(CMP_STR):
            for name_str in node.get_property(CMP_STR):
                if name_str not in generic_names:
                    ic_strs.add(name_str)

    # Use "Unknown" if no names could be determined
    if (len(ic_strs) == 0):
        ic_strs.add("Unknown")

    return list(ic_strs)

def get_arch(dtb_obj, linux_kernel_path=None):

    '''
    Use DTB contents to infer architecture, or Linux kernel path if available
    '''

    # Linux kernel path provided, grab arch from there
    if linux_kernel_path:
        dir_arr = linux_kernel_path.split(os.sep)
        if "arch" in dir_arr:
            return dir_arr[dir_arr.index("arch") + 1]
        else:
            return None

    # Infer arch based on generated signature file
    dtb_cmp_strs = get_cmp_strs(dtb_obj)
    for arch in UNIQUE_DEVS_BY_ARCH:
        intersecting_devs = set(dtb_cmp_strs).intersection(set(UNIQUE_DEVS_BY_ARCH[arch]))
        if len(intersecting_devs):
            return arch

    return None

########################################################################################################################
# QEMU HELPER FUNCS
########################################################################################################################

# TODO: rewrite getters to use a command base?

def get_all_qemu_strs_by_arch(arch, get_cpus=True, get_devs=True):

    '''
    Get all QEMU supported CPUs and/or devices for a given architecture, across all boards
    '''

    strs_set = set()

    if arch not in ARCH_TO_QEMU_BIN.keys():
        return None

    qemu_bin = ARCH_TO_QEMU_BIN[arch]
    qemu_machines = get_qemu_machines(qemu_bin)

    for qemu_machine in qemu_machines:

        if (qemu_machine.lower() == "none"):
            continue

        if get_cpus:
            strs_set.update(get_qemu_cpus(qemu_bin, qemu_machine))
        if get_devs:
            strs_set.update(get_qemu_devices(qemu_bin, qemu_machine))

    return list(strs_set)

def get_qemu_machines(qemu_path):

    '''
    Parsing of qemu output to get a list of supported board/machine definitions.
    '''

    proc = subprocess.run([qemu_path, "-M", "help"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_output = proc.stdout.decode(STR_ENCODING) + proc.stderr.decode(STR_ENCODING)
    machines = []

    for line in cmd_output.splitlines():
        if not line.startswith("Supported machines are:"):
            machines.append(line.strip().split(" ")[0])

    assert(len(machines) > 0)
    return machines

def get_qemu_devices(qemu_path, qemu_machine):

    '''
    Parsing of qemu output to get a list of supported devices.
    '''

    proc = subprocess.run([qemu_path, "-M", qemu_machine, "-device", "help"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_output = proc.stdout.decode(STR_ENCODING) + proc.stderr.decode(STR_ENCODING)
    devices = []

    # Parse into device name and description
    for line in cmd_output.splitlines():
        if line.startswith("name"):
            data = line.split("\"", 2)
            #devices.append((data[1], data[2][2:]))
            devices.append(data[1])

    assert(len(devices) > 0)
    return devices

def get_qemu_cpus(qemu_path, qemu_machine):

    '''
    Parsing of qemu output to get a list of supported cpus.
    '''

    proc = subprocess.run([qemu_path, "-M", qemu_machine, "-cpu", "help"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_output = proc.stdout.decode(STR_ENCODING) + proc.stderr.decode(STR_ENCODING)
    cpus = []

    for line in cmd_output.splitlines():
        if not line.startswith("Available CPUs:"):

            # qemu-system-mips does labeling "MIPS 'cpu_name'"
            if "MIPS \'" in line:
                cpus.append(line.strip().replace("\'", "").split(" ")[1])
            # qemu-system-ppc does labeling "PowerPC cpu_name notes"
            elif "PowerPC " in line:
                cpus.append(line.strip().split(" ")[1])
            else:
                cpus.append(line.strip())

    assert(len(cpus) > 0)
    return cpus

########################################################################################################################
# MISC HELPER FUNCS
########################################################################################################################

def grouper(iterable, n, fill_value=None):

    """
    Collect data into fixed-length chunks or blocks
    Ex: grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    """

    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fill_value)

def tupler(iterable, tuple_len):

    """
    Collect data into chunks of len, i.e tuples
    """

    return list(grouper(iterable, tuple_len))

def file_exists(parser, fp):

    '''
    Helper for arg parsing, check file existence
    '''

    if not os.path.isfile(fp):
        parser.error("The file {0} doesn't exist".format(fp))
    else:
        return fp

def get_fuzzy_match(needle, haystack_list, threshold = 90, verbose = False):

    '''
    Use fuzzy string matching to find close needle in haystack_list
    '''

    name_score_tuple = fzy_proc.extractOne(needle, haystack_list, score_cutoff=threshold)
    if name_score_tuple:
        if verbose:
            print("[FUZZY_MATCH] %s : %s" % (needle, name_score_tuple[0]))
        return name_score_tuple[0]
    else:
        return None

def get_fuzzy_matches(needle_list, hastack_list, threshold = 90, verbose = False):

    '''
    Use fuzzy string matching to count the number of needles with close matches in haystack_list
    '''

    matches = []

    for needle in needle_list:
        close_match = get_fuzzy_match(needle, hastack_list, threshold, verbose)
        if close_match:
            matches.append(close_match)

    return matches

def strip_vendor_prefix(cmp_str):

    '''
    Strip vendor name prefixes, if any. Ex. "arm,gic-v3" -> "gic-v3"
    '''

    return (cmp_str.split(",")[1] if (len(cmp_str.split(",")) == 2) else cmp_str)

def cmp_str_to_sloc(cmp_str):

    '''
    Get SLOC for a given compatible string, if that data is available
    '''

    # Check that we have SLOC data available
    try:
        DRIVER_NAME_TO_SLOC
    except:
        return None

    # Search for the compatible string, average multiple entries
    sloc_cnts_for_cmp_str = []
    for cmp_str_list, sloc_cnt in DRIVER_NAME_TO_SLOC.items():
        if cmp_str in cmp_str_list:
            sloc_cnts_for_cmp_str.append(sloc_cnt)

    if sloc_cnts_for_cmp_str:
        return stats.mean(sloc_cnts_for_cmp_str)
    else:
        return None


