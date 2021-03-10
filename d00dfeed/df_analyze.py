#! /usr/bin/python3

# External deps
import os, sys, argparse, logging, errno, struct, time, json, re, pygount
from multiprocessing import Pool, Manager
from typing import List, Set, Tuple, Dict, Optional, Union, BinaryIO

# Internal deps
sys.path.append("." + os.sep + "analyses")
from df_common import *
from df import Dtb
import analyses_common as ac

########################################################################################################################
# GLOBAL CONSTS
########################################################################################################################

MAGIC_LIST = [(0xd00dfeed, 4)]

########################################################################################################################
# FILE PROCESSING
########################################################################################################################

def get_file_list(arg_parser: argparse.ArgumentParser, input_path: str) -> List[str]:

    '''
    Return list of absolute file paths to process based on input_path.
    If input_path is a file, list has only one entry (the file).
    If input_path is a directory, recursively find all files in dir and nested sub-dirs.
    '''

    file_list = list()

    if os.path.isfile(input_path):
        file_list.append(os.path.abspath(input_path))
    elif os.path.isdir(input_path):
        for dir_path, _, file_names in os.walk(input_path):
            for file in file_names:
                file_list.append(os.path.abspath(os.path.join(dir_path, file)))
    else:
        arg_parser.error("Path \'{}\' not file or directory".format(input_path))

    # TODO: why is this necessary?
    for idx, file in enumerate(file_list):
        if not os.path.exists(file):
            del file_list[idx]

    return file_list

def check_magic(file_ptr: BinaryIO, offset_start: int) -> Tuple[bool, Optional[str]]:

    '''
    Read from file pointer at the specified offset, check if value matches a known magic.
    '''

    for magic, magic_len in MAGIC_LIST:

        file_ptr.seek(offset_start, os.SEEK_SET)
        bytes_read = file_ptr.read(magic_len)

        if (magic_len == 1):
            fmt_str = 'B'
        elif (magic_len == 2):
            fmt_str = 'H'
        elif (magic_len == 4):
            fmt_str = 'L'
        elif (magic_len == 8):
            fmt_str = 'Q'
        else:
            raise NotImplementedError

        if (len(bytes_read) == magic_len):
            if (struct.unpack(('>' + fmt_str), bytes_read)[0] == magic):
                return True, '>'
            elif (struct.unpack(('<' + fmt_str), bytes_read)[0] == magic):
                return True, '<'

    return False, None

def get_dtb_files(file_list: List[str]) -> List[str]:

    '''
    From the list of files passed in, return the subset that are DTBs
    '''

    dtb_paths = []

    for file_path in file_list:
        try:
            file_ptr = open(file_path, "rb")
            match, _ = check_magic(file_ptr, 0)
            if match:
                dtb_paths.append(file_path)
        except Exception as e:
            logging.error("{}".format(e))
            return dtb_paths

    return dtb_paths

def write_dtb_stats_json(stats_dict: Dict[str, Optional[Union[int, str, List[str]]]], full_path: str) -> None:

    '''
    Write a DTB stats file to JSON
    '''

    if os.path.isfile(full_path):
        logging.warning("Overwriting \'{}\'".format(full_path))
    with open(full_path, 'w') as json_out:
        json.dump(stats_dict, json_out)

def linux_source_path_to_driver_type(src_path: str) -> str:

    '''
    Get driver class/category from source
    '''

    DRV_DIR = 'drivers'

    # These sub-dirs of /driver are actually a category, we need the next subdir to tell what the driver is for
    SPECIAL_PARENT_DIRS = {'input', 'iio', 'hsi', 'video', 'net', 'power', 'soc'}

    if DRV_DIR in src_path:

        # Get next subdir from 'drivers'
        path_components = os.path.normpath(src_path).split(os.sep)
        class_idx = (path_components.index(DRV_DIR) + 1)
        dev_class = path_components[class_idx]

        # Use next two subdirs in cases where that provides useful info
        if (dev_class in SPECIAL_PARENT_DIRS) and (not path_components[class_idx + 1].endswith(".c")):
            dev_class = (dev_class + os.sep + path_components[class_idx + 1])

        return dev_class

    else:

        return 'OTHER'

def get_all_linux_driver_sloc_cnts(linux_top_level_dir: str, max_workers: int) -> Tuple[Dict[str, float], Dict[Tuple[str, ...], str]]:

    '''
    Parsing of grep output to get compatible strings and corresponding SLOC counts
    '''

    cmp_str_to_type: Dict[Tuple[str, ...], str] = {}
    src_to_cmp_strs: Dict[str, List[str]] = {} # TODO: use default dict to avoid key check

    # Change into linux dir, recursive grep for C source files mentioning compatible strings
    grep_cmd = ["""grep -r -i --include \*.c -o '.compatible = \".*\"'""" + " " + linux_top_level_dir]
    cmd_output = subprocess.check_output(grep_cmd, shell=True).decode(STR_ENCODING)
    assert(len(cmd_output) > 0)

    # Multiple compatible strings per source file
    for line in cmd_output.splitlines():
        src_path = line.split(":")[0]
        if src_path not in src_to_cmp_strs:
            src_to_cmp_strs[src_path] = []
        cmp_str = re.findall(r'"(.*?)"', line.split(":")[1])[0]
        src_to_cmp_strs[src_path].append(cmp_str)

    assert(len(src_to_cmp_strs) > 0)
    proc_pool_driver_src = Pool(max_workers)
    manager = Manager()
    cmp_str_to_sloc: Dict[str, float] = manager.dict()

    for src_path in src_to_cmp_strs:
        cmp_str_tuple: Tuple[str, ...] = tuple(src_to_cmp_strs[src_path])
        cmp_str_to_type[cmp_str_tuple] = linux_source_path_to_driver_type(src_path)
        proc_pool_driver_src.apply_async(worker_get_single_linux_driver_sloc_cnt, (src_path, cmp_str_tuple, cmp_str_to_sloc,))

    proc_pool_driver_src.close()
    proc_pool_driver_src.join()

    assert(len(cmp_str_to_sloc) > 0)
    return cmp_str_to_sloc, cmp_str_to_type

########################################################################################################################
# WORKER THREAD CALLBACKS
########################################################################################################################

# No typing b/c stats: Dict[str, Optional[Union[int, str, List[str]]]] can't guarantee .extend()
def worker_process_dtb_file(input_file_path, is_linux, output_dir_path):

    '''
    Worker func to write the stats JSON for a single DTB.
    '''

    stats = {}
    stats[JSON_CPU] = []
    stats[JSON_INT] = []
    stats[JSON_CMP_STR] = []
    stats[JSON_PRI_CMP_STR] = []

    try:
        file_ptr = open(input_file_path, "rb")
        match, _ = check_magic(file_ptr, 0)
        if match:

            logging.info("Processing \'{}\'".format(input_file_path))

            dtb = Dtb(file_ptr)
            stats_json_id = ("-" + str(os.getpid()) + "-" + str(int(time.time())))
            stats_json_name = (os.path.basename(os.path.normpath(input_file_path)) + stats_json_id + ".json")
            stats_json_path = os.path.join(output_dir_path, stats_json_name)

            # Collect DTB stats
            arch_str = get_arch(dtb, input_file_path) if is_linux else get_arch(dtb)
            mmio_node_cnt = len(get_mmio_nodes(dtb))
            primary_cmp_strs = get_cmp_strs(dtb, primary_only=True)
            cmp_strs = get_cmp_strs(dtb, primary_only=False)
            cpu_strs = get_cpu(dtb)
            int_strs = get_int(dtb)

            # Build JSON
            stats[JSON_ARC] = arch_str
            stats[JSON_CMP_CNT] = len(cmp_strs)
            stats[JSON_PRI_CMP_CNT] = len(primary_cmp_strs)
            stats[JSON_MIO_CNT] = mmio_node_cnt
            stats[JSON_CPU].extend(cpu_strs)
            stats[JSON_INT].extend(int_strs)
            stats[JSON_CMP_STR].extend(cmp_strs)
            stats[JSON_PRI_CMP_STR].extend(primary_cmp_strs)

            # Write JSON
            write_dtb_stats_json(stats, stats_json_path)

    except Exception as e:
        logging.error("{}".format(e))
        return

def worker_get_single_linux_driver_sloc_cnt(file_path: str, cmp_str_tuple: Tuple[str], shared_dict: Dict[Tuple[str], float]) -> None:

    '''
    Worker func to collect SLOC and add to shared manager.dict()
    '''

    sloc_cnt = pygount.SourceAnalysis.from_file(file_path, 'driver_sloc').code
    shared_dict[cmp_str_tuple] = sloc_cnt

########################################################################################################################
# DRIVER
########################################################################################################################

if __name__ == "__main__":

    arg_parser = argparse.ArgumentParser(description="Get statistics for DTB file(s)")
    arg_parser.add_argument(
            'input_file_or_dir',
            type=str,
            help="DTB file or directory containing multiple DTB files.")
    arg_parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join(os.path.abspath(os.sep), "tmp", "df_out"),
            help="Directory to output stats JSONs.(Default == /tmp/df_out")
    arg_parser.add_argument(
            '--max-workers',
            type=int,
            default=os.cpu_count(),
            help="Maximum number parallel worker processes (Default == CPU count)")
    arg_parser.add_argument(
            '--linux-src-dir',
            action="store_true",
            default=False,
            help="The input directory is Linux source code. \
                If flag present, will get driver SLOC and infer DTB architecture from path")

    # Setup
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="[%(processName)s]:%(levelname)s:%(message)s")
    args = arg_parser.parse_args()
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)

    # Peripheral Driver SLOC
    if args.linux_src_dir:

        # Compute SLOC, get device types
        sloc_data_tuple_key, type_data_tuple_key = get_all_linux_driver_sloc_cnts(args.input_file_or_dir, args.max_workers)

        # Generate file for use by other analyses
        SLOC_FILE = os.path.join(GEN_FILE_DIR, "sloc_cnt.py")
        ac.write_hdr_for_py_file(SLOC_FILE, "THIS FILE WAS AUTO GENERATED BY ./df_analyze.py")
        ac.write_dict_to_py_file(SLOC_FILE, "DRIVER_NAME_TO_SLOC", sloc_data_tuple_key)

        # Generate file for use by other analyses
        TYPE_FILE = os.path.join(GEN_FILE_DIR, "driver_types.py")
        ac.write_hdr_for_py_file(TYPE_FILE, "THIS FILE WAS AUTO GENERATED BY ./df_analyze.py")
        ac.write_dict_to_py_file(TYPE_FILE, "DRIVER_NAME_TO_TYPE", type_data_tuple_key)

    # DTB Parallel processing
    proc_pool_dtb = Pool(args.max_workers)
    logging.info("Processing file(s)...")
    files_to_search = get_file_list(arg_parser, args.input_file_or_dir)
    for file_path in files_to_search:
        proc_pool_dtb.apply_async(worker_process_dtb_file, (file_path, args.linux_src_dir, args.output_dir,))
    proc_pool_dtb.close()
    proc_pool_dtb.join()
    logging.info("Done. See \'{}\' for results.".format(args.output_dir))