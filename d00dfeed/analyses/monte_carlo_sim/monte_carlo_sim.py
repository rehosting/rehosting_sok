#! /usr/bin/python3

# External deps
import sys, os, logging, argparse, random, statistics, copy, json
import matplotlib

# Allow graph creation without X11 (ex. detached from screen/ssh)
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from multiprocessing import Pool, Manager
from pathlib import Path
from typing import List, Set, Tuple, Dict, Optional, Union

# Internal deps
os.chdir(sys.path[0])
sys.path.append("..")
sys.path.append(".." + os.sep + "..")
from df import Dtb
import analyses_common as ac
import df_common as dfc
import df_analyze as dfa

########################################################################################################################
# HELPERS
########################################################################################################################

def init_qemu_peripheral_list() -> List[str]:

    '''
    Get lists of all QEMU-supported peripherals
    '''

    qemu_devs: Set[str] = set()

    qemu_devs.update(dfc.get_all_qemu_strs_by_arch('arm', get_cpus=True, get_devs=True))
    qemu_devs.update(dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=True, get_devs=True))
    qemu_devs.update(dfc.get_all_qemu_strs_by_arch('mips', get_cpus=True, get_devs=True))
    qemu_devs.update(dfc.get_all_qemu_strs_by_arch('ppc', get_cpus=True, get_devs=True))

    return list(qemu_devs)

def get_next_dtb(artifact_path_list: List[str]) -> Tuple[str, List[str]]:

    '''
    Pick the next DTB (or representative stats JSON) at random, from the remaining.
    '''

    idx = random.randrange(len(artifact_path_list))
    artifact_path = artifact_path_list[idx]
    del artifact_path_list[idx]

    return artifact_path, artifact_path_list

def rehost(artifact_path: str, P_q: List[str], P_m: List[str], avg_sloc_by_arch: Dict[str, float]) -> Tuple[int, List[str], float]:

    '''
    Rehost the SoC represented by a given DTB (or representative stats JSON):
        1. Get all primary compatible strings
        2. Use QEMU implementations or prior manually implementations for any matching peripherals
        3. Manually implement the remaining unsupported peripherals

    P_q == QEMU supported peripherals (may be empty)
    P_m == Manually implemented peripherals (simulated)
    P_u == Unimplemented peripherals

    Returns the count of peripherals that needed to be manually implemented, the updated list, and, optionally, SLOC
    for the newly implemented
    '''

    P_m_len_in = len(P_m)
    data: Dict[str, str] = {'Empty': 'Empty'}  # This typdef doesn't cover all cases. TODO: Add full typedef to common file

    # Start of by assuming we have to implement all primary compatible strings
    # Note strip of vendor prefix, and removal of duplicates
    if artifact_path.endswith(".json"):
        data = json.load(open(artifact_path))
        P_u = set(data[dfc.JSON_PRI_CMP_STR])
    else:
        P_u = set([dfc.strip_vendor_prefix(x) for x in dfa.get_cmp_strs(Dtb(artifact_path), primary_only=True)])

    cmp_strs = list(P_u)

    # Fuzzy match QEMU supported and previously [theoretically] implemented
    already_qemu_supported_subset = set(dfc.get_fuzzy_matches(cmp_strs, P_q, threshold=95, verbose=False))
    already_manually_implemented_subset = set(dfc.get_fuzzy_matches(cmp_strs, P_m, threshold=95, verbose=False))

    # Compute remainder we must implement
    P_u = P_u.difference(already_qemu_supported_subset)
    P_u = P_u.difference(already_manually_implemented_subset)

    # Implement those, in theory, to support the next iteration
    P_m.extend(list(P_u))

    # Optionally track SLOC for new implementsions
    P_u_sloc = 0.0
    if ('Empty' not in avg_sloc_by_arch.keys()) and artifact_path.endswith(".json"):
        for cmp_str in P_u:
            sloc_cnt = dfc.cmp_str_to_sloc(cmp_str)

            # We have SLOC data for this driver
            if sloc_cnt:
                P_u_sloc += sloc_cnt
            # We don't have SLOC data for this driver, use architecture average instead
            else:
                P_u_sloc += avg_sloc_by_arch[data[dfc.JSON_ARC]]

    # Post-condition
    assert(len(P_m) >= P_m_len_in)

    # Report how many had to be implemented, return new manually impelmented list
    return len(P_u), P_m, P_u_sloc

def write_list_data_file(file_name: str, data_list: Union[List[int], List[float]]) -> None:

    '''
    Write a list of data to file, one element per line (for LaTeX graphing)
    '''

    with open(file_name, 'w') as f:
        for elem in data_list:
            f.write(str(elem) + os.linesep)

def write_dict_of_list_data_file(file_name: str, data_dict_of_list: Union[Dict[int, List[int]], Dict[int, List[float]]]) -> None:

    '''
    Write a dict of list data to file, { key elem_1, elem2, ... elem_N } (for LaTeX graphing)
    '''

    with open(file_name, 'w') as f:
        for k, v in data_dict_of_list.items():
            f.write(str(k) + ' ' + ' '.join(str(e) for e in v) + os.linesep)

########################################################################################################################
# WORKER THREAD CALLBACKS
########################################################################################################################

def worker_run_simulation(
    rehost_cnt: int,                                # Number of DTBs to randomly select for rehosting
    P_q: List[str],                                 # List of peripherals supported in QEMU
    avg_sloc_by_arch: Dict[str, float],             # Avg SLOC for a driver, by arch (if availbile)
    artifact_path_list_in: List[str],               # List of all DTB paths or all JSON summary stat paths
    shared_total_sloc_list: List[float],            # List of total SLOC implemented per simulation (shared between processes)
    shared_total_cnt_list: List[int],               # List of total peripherals implemented per simulation (shared between processes)
    shared_median_cnt_list: List[float],            # List of median unimplemented peripherals per SoC (shared between processes)
    shared_avg_cnt_list: List[float],               # List of average unimplemented peripherals per SoC (shared between processes)
    shared_unimp_cnt_dict: Dict[int, List[int]],    # Dict of lists: unimplemented peripheral count of reach SoC rehosted
    shared_total_cnt_dict: Dict[int, List[int]]     # Dict of lists: total unimplemented peripheral count at the time of each rehost attempt
    ) -> None:

    '''
    P_q == QEMU supported peripherals
    P_m == Manually implemented peripherals (simulated)
    P_u == Unimplemented peripherals
    '''

    P_m_per_dtb_list: List[int] = []
    P_m_sloc_per_dtb_list: List[float] = []
    P_m: List[str] = []
    artifact_path_list: List[str] = copy.deepcopy(artifact_path_list_in)

    # Simulate rehosting Y devices, implementing unsupported peripherals each time
    for j in range(rehost_cnt):

        try:

            # Simulate rehost
            artifact_path, artifact_path_list = get_next_dtb(artifact_path_list)
            P_u_len, P_m, P_u_sloc = rehost(artifact_path, P_q, P_m, avg_sloc_by_arch)
            P_m_len = len(P_m)

            # Collect per-rehost stats (private buf, only this thread)
            P_m_per_dtb_list.append(P_u_len)
            P_m_sloc_per_dtb_list.append(P_u_sloc)

            # Collect per-rehost stats (shared buf, written to by other threads, interweaving possible)
            shared_unimp_cnt_dict[j].append(P_u_len)
            shared_total_cnt_dict[j].append(P_m_len)

            # Print intermediate simulation results
            logging.info("Rehosted \'{}\', new manually implemented: {}, total manually implemented: {}".format(
                artifact_path.split(os.sep)[-1],
                P_u_len,
                P_m_len))

        except Exception as e:
            logging.error(repr(e))

    # Collect simulation stats
    P_m_len = len(P_m)
    P_m_median = statistics.median(P_m_per_dtb_list)
    P_m_average = statistics.mean(P_m_per_dtb_list)
    P_m_sloc = sum(P_m_sloc_per_dtb_list)
    shared_median_cnt_list.append(P_m_median)
    shared_avg_cnt_list.append(P_m_average)
    shared_total_cnt_list.append(P_m_len)
    shared_total_sloc_list.append(P_m_sloc)

    # Print final simulation results
    logging.info("Simulation result: {} median manually implemented peripherals per DTB, {} average, {} total".format(
        P_m_median,
        P_m_average,
        P_m_len))

########################################################################################################################
# DRIVER
########################################################################################################################

if __name__ == "__main__":

    arg_parser = argparse.ArgumentParser(description="Run Monte Carlo rehosting simulation.")
    arg_parser.add_argument(
        'input_file_or_dir',
        type=str,
        help="Directory containing multiple DTB files or multiple JSON summary stats generated from DTB files.")
    arg_parser.add_argument(
        '--rehost-cnt',
        type=int,
        default=100,
        required=False,
        help="Number devices to rehost each iteration (Default == 100).")
    arg_parser.add_argument(
        '--iter-cnt',
        type=int,
        default=1000,
        required=False,
        help="Number of simulation iterations (Default == 1000).")
    arg_parser.add_argument(
        '--max-workers',
        type=int,
        default=os.cpu_count(),
        help="Maximum number parallel worker processes (Default == CPU count)")
    arg_parser.add_argument(
        '--output-dir',
        type=str,
        default=Path(__file__).resolve().parent,
        help="Directory to output stats JSONs.(Default == ./")
    arg_parser.add_argument(
        '--no-qemu',
        default=False,
        action='store_true',
        help="Do NOT consider existing QEMU device implementations in simulation")

    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="[%(processName)s]:%(levelname)s:%(message)s")
    args = arg_parser.parse_args()

    track_sloc = False
    input_files = dfa.get_file_list(arg_parser, args.input_file_or_dir)
    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    if args.no_qemu:
        logging.info("Not considerting QEMU-supported peripherals!")
        P_q = list()
    else:
        logging.info("Gathering QEMU-supported peripherals...")
        P_q = init_qemu_peripheral_list()

    avg_sloc_by_arch: Dict[str, float] = {'Empty': 0.0}

    # USECASE 1 - You've run 0xD00DFEED on the Linux kernel, you've got JSONS and SLOC data
    # Run simulations with stats summary JSONS
    if all(fn.endswith(".json") for fn in input_files):

        # If SLOC data is available, we'll track it as part of the simulation
        if (os.path.exists(os.path.join(dfc.GEN_FILE_DIR, "sloc_cnt.py"))):

            artifact_path_list = input_files
            logging.info("Gathering SLOC data...")

            sys.path.append(dfc.GEN_FILE_DIR)
            sys.path.append("..")
            from sloc_cnt import DRIVER_NAME_TO_SLOC
            from graph_dd_sloc_by_arch import get_sloc_avg_and_list_by_arch

            cmp_by_arch = ac.build_dict_two_lvl_cnt(artifact_path_list, dfc.JSON_ARC, dfc.JSON_CMP_STR)
            avg_sloc_by_arch, sloc_list_by_arch = get_sloc_avg_and_list_by_arch(cmp_by_arch, verbose = False)

        logging.info("Using JSON files...")

    # USECASE 2 - You have a bunch of DTBs of unknown origin
    # Run simulations with actual DTB files
    # Don't track SLOC
    else:

        logging.info("Finding DTB files...")
        artifact_path_list = dfa.get_dtb_files(input_files)

    logging.info("Setuping up worker pool...")
    sim_proc_pool = Pool(args.max_workers)
    manager = Manager()

    # End of simulation data (represents all rehost attempts)
    # List shared between processes
    shared_total_sloc_list: List[int] = manager.list()
    shared_total_cnt_list: List[int] = manager.list()
    shared_median_cnt_list: List[int] = manager.list()
    shared_avg_cnt_list: List[float] = manager.list()

    # Per-rehost data (represents rehost attempts {1, 2, 3 .. N})
    # Dict of lists shared between processes
    shared_unimp_cnt_dict: Dict[int, List[int]] = manager.dict()
    shared_total_cnt_dict: Dict[int, List[int]] = manager.dict()
    for i in range(args.rehost_cnt):
            shared_unimp_cnt_dict[i] = manager.list()
            shared_total_cnt_dict[i] = manager.list()

    # Run the simulation X times
    logging.info("Simulating {} {}-device rehost efforts...".format(args.iter_cnt, args.rehost_cnt))
    for i in range(args.iter_cnt):
        sim_proc_pool.apply_async(worker_run_simulation,
            (
                args.rehost_cnt,
                P_q,
                avg_sloc_by_arch,
                artifact_path_list,
                shared_total_sloc_list,
                shared_total_cnt_list,
                shared_median_cnt_list,
                shared_avg_cnt_list,
                shared_unimp_cnt_dict,
                shared_total_cnt_dict
            )
        )
    sim_proc_pool.close()
    sim_proc_pool.join()

    # Save off data for later use (ex. LaTeX graphs)
    write_list_data_file(os.path.join(args.output_dir, "monte_median_all_sims.dat"), shared_median_cnt_list)
    write_list_data_file(os.path.join(args.output_dir,"monte_avg_all_sims.dat"), shared_avg_cnt_list)
    write_list_data_file(os.path.join(args.output_dir,"monte_total_all_sims.dat"), shared_total_cnt_list)
    write_list_data_file(os.path.join(args.output_dir,"monte_sloc_all_sims.dat"), shared_total_sloc_list)
    write_dict_of_list_data_file(os.path.join(args.output_dir,"monte_totals_per_rehost.dat"), shared_total_cnt_dict)
    write_dict_of_list_data_file(os.path.join(args.output_dir,"monte_unimp_per_rehost.dat"), shared_unimp_cnt_dict)

    # Graph 1 - Median manually implemented per DTB
    fig_1 = plt.figure(1)
    ac.graph_simple_histogram(
        shared_median_cnt_list,
        "Median Manually Implemented Peripherals per SoC",
        "Frequency",
        "Median Manually Implemented Peripherals per SoC for {} Simulations of {}-device Rehost".format(args.iter_cnt, args.rehost_cnt)
    )
    plt.savefig(os.path.join(args.output_dir,'monte_median_p_SoC.png'), dpi=200, bbox_inches='tight')

    # Graph 2 - Total implemented each simulation
    fig_2 = plt.figure(2)
    ac.graph_simple_histogram(
        shared_total_cnt_list,
        "Total Manually Implemented Peripherals per Simulation",
        "Frequency",
        "Total Manually Implemented Peripherals per Simulation for {} Simulations of {}-device Rehost".format(args.iter_cnt, args.rehost_cnt)
    )
    plt.savefig(os.path.join(args.output_dir,'monte_total_p.png'), dpi=200, bbox_inches='tight')
