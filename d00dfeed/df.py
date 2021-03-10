#! /usr/bin/python3

import fdt, coloredlogs, logging, os, io, sys, argparse, copy
from df_common import *

########################################################################################################################
# DTB CLASS - Wrapper for fdt lib, higher-level actions
########################################################################################################################

class Dtb:

    def __init__(self, dtb_file):

        '''
        Init the dtb object, loaded from file, for use by class funcs
        Init mapping of node names to their paths
        '''

        if isinstance(dtb_file, io.BufferedIOBase):
            dtb_file.seek(0)
            dtb_data = dtb_file.read()
        elif os.path.isfile(dtb_file):
            with open(dtb_file, "rb") as f:
                dtb_data = f.read()
        else:
            raise FileNotFoundError

        self.dtb_obj = fdt.parse_dtb(dtb_data)
        self._update_name_path_map()

    # ------------------------------------------------------------------------------------------------------------------
    # DTB CLASS - Internal functions
    # ------------------------------------------------------------------------------------------------------------------

    def _update_name_path_map(self):

        '''
        Call after node additions/deletions to maintain consistent view of the DTB.
        '''

        self.name_path_map = dict()
        for path, nodes, props in self.dtb_obj.walk():
            name = self.dtb_obj.get_node(path).name
            containing_path = path.replace("/" + name, '')
            self.name_path_map[name] = Containing_full_path_tuple(containing_path, path)

    # ------------------------------------------------------------------------------------------------------------------
    # DTB CLASS - Query functions
    # ------------------------------------------------------------------------------------------------------------------

    def get_devs_by_prop(self, prop, verbose = False):

        '''
        Get list of devices that posses a specific property, ex:
        "status" -> devices that can be enabled/disabled
        "compatible" -> devices that list a compatible driver name
        '''

        dev_list = []
        prop_list = self.dtb_obj.search(prop)
        if verbose:
            logging.info("DTB - Devices with property \'{}\':".format(prop))

        for prop in prop_list:
            dev = prop.parent.name
            dev_list.append(Dev_prop_vals(dev, prop.data))
            if verbose:
                logging.info("\t{:<30} < {} >".format(dev, prop.data))

        return dev_list

    def get_nodes_by_prop(self, prop, verbose = False):

        '''
        Get list of nodes that posses a specific property
        '''

        node_list = []
        prop_list = self.dtb_obj.search(prop)
        if verbose:
            logging.info("DTB - Nodes with property \'{}\':".format(prop))

        for prop in prop_list:
            node = prop.parent
            node_list.append(node)
            if verbose:
                logging.info("\t{:<30} < {} >".format(node.name, prop.data))

        return node_list

    def get_node_by_name(self, dev_name):

        '''
        Return node corresponding to DTB device name
        '''

        if (dev_name in self.name_path_map):
            dev_path = self.name_path_map[dev_name].containing_path
            return self.dtb_obj.get_node(dev_path + "/" + dev_name)
        else:
            return None

    # ------------------------------------------------------------------------------------------------------------------
    # DTB CLASS - Physical address translation
    # ------------------------------------------------------------------------------------------------------------------

    def get_dev_mem_maps(self, child):

        '''
        Get the memory ranges for a memory-mapped device
        Based on v0.2 spec (https://github.com/devicetree-org/devicetree-specification/releases/download/v0.2/devicetree-specification-v0.2.pdf)
        Loosely based on kernel's "__of_translate_address" (https://elixir.bootlin.com/linux/v4.4.138/source/drivers/of/address.c#L550)
        NOTE: This is a highly experimental feature, we make no guarantees about accuracy
        '''

        mem_map_pairs = []

        # Validate existence of register property
        if not (child.exist_property(REG_STR)):
            return mem_map_pairs

        # Validate structure of register property
        child_reg_prop = child.get_property(REG_STR)
        if not (isinstance(child_reg_prop, fdt.PropWords) and (len(child_reg_prop) % 2 == 0)):
            return mem_map_pairs

        # Create a running copy, will update it's reg tuples as we traverse the tree upward and apply translations
        running_child = copy.deepcopy(child)
        assert(running_child.get_property(REG_STR).data == child_reg_prop.data)

        # Walk up to root and apply findings
        while (child.parent and child.parent.name != '/'):

            parent = child.parent

            # Apply bus translation
            running_addr = self.do_bus_addr_translanslation(running_child, parent)
            running_child.props[:] = [x for x in running_child.props if x != running_child.get_property(REG_STR)]   # Delete
            running_child.append(fdt.PropWords(REG_STR, *list(chain(*running_addr))))                               # Replace

            # Move up one level for next iteration
            child = parent

        for base, size in tupler(running_child.get_property(REG_STR), 2):
            mem_map_pairs.append(Dev_mem_map(base, size))

        return mem_map_pairs

    def do_bus_addr_translanslation(self, child, parent):

        '''
        Translate child regs addrs into parent's addr space
        '''

        translated_regs = []
        child_reg_tuples = self.combine_addr_size_cells(child, REG_STR)

        # 1:1 translation, return early
        if ((not parent.exist_property(RNG_STR)) or
            ("empty" in parent.get_property(RNG_STR).data)):
            return child_reg_tuples

        parent_range_tuples = self.combine_addr_size_cells(parent, RNG_STR)

        # Translate to parent address space
        for child_base, child_size in child_reg_tuples:
            translated_base = -1
            for child_bus_addr, parent_bus_addr, length in parent_range_tuples:
                if ((child_bus_addr <= child_base) and (child_base <= (child_bus_addr + length))):
                    translated_base = (child_base - child_bus_addr) + parent_bus_addr
                    translated_regs.append((translated_base, child_size))
                    break

        if (translated_base == -1):
            logging.error("Could not translate child ({}) regs to parent ({}) range!".format(child.name, parent.name))
            return child_reg_tuples

        return translated_regs

    def combine_addr_size_cells(self, node, prop_str):

        '''
        For "ranges" and "regs" properties, apply #address-cells and #size-cells compressions so that
        multi-cell values are represented buy a single value in the returned tuples
        '''

        # Get reasonable defaults for board
        root = self.dtb_obj.get_node("/")
        assert(root.exist_property(NAC_STR) and node.parent.exist_property(NSC_STR))
        default_num_addr_cells = root.get_property(NAC_STR).data[0]
        default_num_size_cells = root.get_property(NSC_STR).data[0]

        # Safe fetch values from nodes
        combined_result = []
        num_addr_cells = self.get_safe_single_value_prop(node, NAC_STR, default_num_addr_cells, [0])
        num_size_cells = self.get_safe_single_value_prop(node, NSC_STR, default_num_size_cells, [0])

        if (prop_str == RNG_STR):

            assert(node.exist_property(RNG_STR) and node.parent.exist_property(NAC_STR))
            parent_num_addr_cells = node.parent.get_property(NAC_STR).data[0]
            tuple_len = num_addr_cells + parent_num_addr_cells + num_size_cells
            range_tuples = tupler(node.get_property(RNG_STR).data, tuple_len)

            # Combine addresses made up of multiple 32-bit numbers
            for range_entry in range_tuples:

                idx, child_addr = self.combine_cells(range_entry, 0, num_addr_cells)
                idx, parent_addr = self.combine_cells(range_entry, idx, (num_addr_cells + parent_num_addr_cells))
                idx, size = self.combine_cells(range_entry, idx, (num_addr_cells + parent_num_addr_cells + num_size_cells))

                combined_result.append((child_addr, parent_addr, size))

            return combined_result

        elif (prop_str == REG_STR):

            assert(node.exist_property(REG_STR))
            tuple_len = num_addr_cells + num_size_cells
            reg_tuples = tupler(node.get_property(REG_STR), tuple_len)

            # Combine addresses made up of multiple 32-bit numbers
            for reg_entry in reg_tuples:

                idx, addr = self.combine_cells(reg_entry, 0, num_addr_cells)
                idx, size = self.combine_cells(reg_entry, idx, (num_addr_cells + num_size_cells))

                combined_result.append((addr, size))

            return combined_result

        else:
            logging.error("Invalid property for address/size combination.")
            return None

    def get_safe_single_value_prop(self, node, prop_str, good_default, bad_default_list):

        '''
        Helper to retrive a property safely - will assume a default if property is missing or
        set to a value that's in the provided list of bad values
        '''

        if (not node.exist_property(prop_str)):
            return good_default
        else:
            prop_val = node.get_property(prop_str).data[0]
            if (prop_val in bad_default_list):
                #logging.warn("Node {} has {} set to {}! Using safe default of {}".format(node.name,
                    #node.get_property(prop_str).name, prop_val, good_default))
                return good_default
            else:
                return prop_val

    def combine_cells(self, cell_list, idx, end_idx):

        '''
        Combine multiple adjacent 32-bit cells in a list
        '''

        output = cell_list[idx]
        num_cells_to_left_shift = 0
        idx += 1

        while (idx < end_idx):
            num_cells_to_left_shift += 1
            output = (output | (cell_list[idx] << (NUM_WIDTH * num_cells_to_left_shift)))
            idx += 1

        return idx, output

    def print_phys_mem_map(self):

        '''
        Reconstruct and print the device's memory map
        '''

        mmio_maps = []
        mmio_map_to_name = {}
        mmio_nodes = self.get_nodes_by_prop(REG_STR)

        # Collect
        for node in mmio_nodes:
            node_mem_maps = self.get_dev_mem_maps(node)
            if node_mem_maps:
                mmio_maps.extend(node_mem_maps)
                for mem_map in node_mem_maps:
                    mmio_map_to_name[mem_map] = node.name

        # Sort
        mmio_maps.sort(key=lambda dev: dev[0])

        # Print
        for mmio_map in mmio_maps:
            logging.info("\t[0x{:08x} - 0x{:08x}] {}".format(
                mmio_map.addr, (mmio_map.addr + mmio_map.size), mmio_map_to_name[mmio_map]))

    # ------------------------------------------------------------------------------------------------------------------
    # DTB CLASS - DTB modification (must call write_dtb() after making the changes!)
    # ------------------------------------------------------------------------------------------------------------------

    def set_property(self, dev_name, prop_str, new_prop):

        '''
        Set an existing property to a new value (overwrite).
        '''

        node = self.get_node_by_name(dev_name)

        if node.exist_property(prop_str):
            logging.info("DTB - Dev: {}, Prop: {} - had old value of {}".format(dev_name, prop_str, node.get_property(prop_str)))
            node.props[:] = [x for x in node.props if x != node.get_property(prop_str)] # Delete

        if isinstance(new_prop, str):
            node.append(fdt.PropStrings(prop_str, new_prop))
        elif isinstance(new_prop, int):
            node.append(fdt.PropWords(prop_str, new_prop))
        else:
            node.append(fdt.PropWords(prop_str, *new_prop))

        logging.info("DTB - Dev: {}, Prop: {} - set to {}!".format(dev_name, prop_str, new_prop))

    def replace_dev(self, old_dev_name, new_dev_name, props={}):

        '''
        Replace an entry in the DTB with a new sibling entry with specified properties
        '''

        # Save path of old device
        assert(old_dev_name in self.name_path_map)
        dev_path = self.name_path_map[old_dev_name].containing_path
        self.name_path_map[new_dev_name] = self.name_path_map[old_dev_name]

        # Remove old device
        self.remove_dev(old_dev_name)

        # Create new device, with no properties yet and add to dtb
        new_node = fdt.Node(new_dev_name)
        self.dtb_obj.add_item(new_node, dev_path, create=True)

        # Set each property
        for prop_name, prop_val in props.items():
            self.set_property(new_dev_name, prop_name, prop_val)

        self._update_name_path_map()

    def remove_dev(self, dev_name):

        '''
        Specify a device to completely remove from the DTB
        '''

        assert(dev_name in self.name_path_map)

        dev_path = self.name_path_map[dev_name].containing_path
        self.dtb_obj.remove_node(dev_name, path=dev_path)
        del self.name_path_map[dev_name]
        logging.info("DTB - Removed {} [{}]".format(dev_name, dev_path))

    def add_virt_mmio_node(self, base_addr, size, int_list, int_parent):

        '''
        Add virtio mmio region for QEMU's use.
        See: https://github.com/qemu/qemu/blob/a2e002ff7913ce93aa0f7dbedd2123dce5f1a9cd/hw/arm/virt.c#L844
        '''

        # Build node
        dev_name = "virt_mmio@{:08x}".format(base_addr)
        node = fdt.Node(dev_name)
        node.append(fdt.PropStrings('compatible', 'virtio,mmio'))
        node.append(fdt.PropWords('reg', base_addr, size, wsize=32))
        node.append(fdt.PropWords('interrupt-parent', int_parent, wsize=32))
        node.append(fdt.PropWords('interrupts', *int_list, wsize=32))
        node.append(fdt.Property('dma-coherent'))

        # Add node to DTB
        self.dtb_obj.add_item(node)
        self._update_name_path_map()

        dev_path = self.name_path_map[dev_name].containing_path
        logging.info("DTB - Added {} [{}]".format(dev_name, dev_path))

    # ------------------------------------------------------------------------------------------------------------------
    # DTB CLASS - File I/O
    # ------------------------------------------------------------------------------------------------------------------

    def write_dts(self, dts_file):

        '''
        Write object to DTS file
        '''

        with open(dts_file, "w") as f:
            f.write(self.dtb_obj.to_dts())

    def write_dtb(self, dtb_file):

        '''
        Write object to DTB file
        '''

        with open(dtb_file, "wb") as f:
            f.write(self.dtb_obj.to_dtb())

########################################################################################################################
# MAIN - Use as standalone util
########################################################################################################################

if __name__ == "__main__":

    coloredlogs.install(level=logging.DEBUG, fmt='%(levelname)s %(name)s %(message)s') # Colored logs w/o timestamp

    parser = argparse.ArgumentParser(description="Parse or modify a Device Tree Blob (DTB)")
    parser.add_argument(
            'dtb',
            type=lambda x: file_exists(parser, x),
            help="Device Tree Blob to parse")
    parser.add_argument(
            '--disable',
            required=False,
            type=str,
            nargs="+",
            help="List of devices to patch out")
    parser.add_argument(
            '--set-property',
            required=False,
            type=str,
            nargs='*',
            action='append',
            help="Provide three arguments to set a property: --set-property dev_name prop_name new_value")
    parser.add_argument(
            '--list-all',
            required=False,
            action='store_true',
            help="List all devices found")
    parser.add_argument(
            '--phys-mem-map',
            required=False,
            action='store_true',
            help="Show physical memory map")
    parser.add_argument(
            '--id-arch',
            required=False,
            action='store_true',
            help="Identify DTB architecture")
    parser.add_argument(
            '--patched-dtb-out',
            required=False,
            type=str,
            help="Filename for output patched DTB")
    parser.add_argument(
            '--dts-out',
            required=False,
            type=str,
            help="Filename for output DTS")

    args = parser.parse_args()

    if args.disable and (args.patched_dtb_out is None):
        parser.error("--disable requires --patched-dtb-out")
        sys.exit(1)

    dtb = Dtb(args.dtb)

    if args.list_all:
        logging.info("DTB - listing all devices:")
        for key, val in dtb.name_path_map.items():
            logging.info("\t{} [{}]".format(key, val.full_path))

    if args.id_arch:
        logging.info("DTB - identifying architecture:")
        logging.info("\t{}".format(get_arch(dtb)))

    if args.phys_mem_map:
        logging.info("DTB - reconstructing physical memory map:")
        dtb.print_phys_mem_map()

    if args.disable:
        for dev_name in args.disable:
            dtb.remove_dev(dev_name)

    # TODO: maybe cleanup this garbage
    if args.set_property:
        for prop in args.set_property:
            assert (len(prop) == 3) # Expecting each to be [devname, propname, newvalue(s)]
            dev_name = prop[0].strip()
            prop_name = prop[1].strip()
            new_prop = prop[2].split(";")
            if len(new_prop) == 1:
                new_prop = prop[2]
            if len(new_prop[len(new_prop)-1]) == 0: # If last element is empty, drop it (still a list though)
                del new_prop[len(new_prop)-1]
            if prop_name in ["ranges"]:
                new_prop[:] = [int(x, 0) for x in new_prop]
            dtb.set_property(dev_name, prop_name, new_prop)

    if args.dts_out:
        dtb.write_dts(args.dts_out)
    if args.patched_dtb_out:
        dtb.write_dtb(args.patched_dtb_out)