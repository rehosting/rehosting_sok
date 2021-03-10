#! /usr/bin/python3

import os, sys, unittest, logging, timeit, random, fdt
import test_common as tc

sys.path.append('../')   # TODO: there's probably a pythonic way to relative import
import df
import df_common as dfc

dtb_objs = dict()
devs_used_by_tests =    [
                        'scu@c000',
                        'spi-nor@0',
                        'interrupt-controller@20a00',
                        'flash@d0000',
                        'mbus-controller@20000',
                        'spi@10600'
                        ]

class test_dtb(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        for input_file in tc.dtb_test_files:
            if os.path.exists(input_file):
                try:
                    logging.info("Parsing DTB file {}...".format(input_file))
                    dtb_objs[input_file] = df.Dtb(input_file)
                except IOError as e:
                    logging.error("({}): {}".format(e.errno, e.strerror))
            else:
                logging.error("{} not found!".format(input_file))

    def test_dev_removal(self):

        '''
        Can we remove a device from the DTB?
        '''

        i = 0
        out_file_name = "patched_test.dtb"
        test_dtb = dtb_objs[tc.to_dtb]
        #rm_dev = random.SystemRandom().choice(list(test_dtb.name_path_map.keys()))
        rm_dev = list(test_dtb.name_path_map.keys())[i]
        rm_dev_path = test_dtb.name_path_map[rm_dev].containing_path

        while ((rm_dev in devs_used_by_tests)     # Don't randomly remove a device we need for another test
            or (rm_dev == '/')                    # Don't remove root node
            or ('@' not in rm_dev)):              # Don't remove a repeating name, only a specific device with an address

            #rm_dev = random.SystemRandom().choice(list(test_dtb.name_path_map.keys()))
            i += 1
            rm_dev = list(test_dtb.name_path_map.keys())[i]
            rm_dev_path = test_dtb.name_path_map[rm_dev].containing_path

        self.assertTrue(test_dtb.dtb_obj.exist_node(rm_dev_path))
        self.assertFalse(rm_dev in devs_used_by_tests)
        logging.debug("Selected device \'{}\' for removal".format(rm_dev))
        test_dtb.remove_dev(rm_dev)
        test_dtb.write_dtb(out_file_name)
        self.assertTrue(os.path.isfile(out_file_name))

        patched_dtb = df.Dtb(out_file_name)
        self.assertTrue(rm_dev not in patched_dtb.name_path_map)
        logging.debug("Device \'{}\' not present in patched DTB".format(rm_dev))
        os.remove(out_file_name)

        logging.debug("TEST 1: DTB patching - device removal OK!")

    def test_prop_swap(self):

        '''
        Can we set the value for an existing property?
        '''

        test_dtb = dtb_objs[tc.to_dtb]
        orig_prop_val = test_dtb.get_node_by_name("mbus-controller@20000").get_property("compatible").data[0]

        test_dtb.set_property("mbus-controller@20000", "compatible", "simple-bus")
        swapped_prop_val = test_dtb.get_node_by_name("mbus-controller@20000").get_property("compatible").data[0]

        # Check prop
        self.assertEqual(swapped_prop_val, "simple-bus")
        self.assertEqual(orig_prop_val, "marvell,mbus-controller")

        logging.debug("TEST 2: DTB patching - property swap OK!")

    def test_dev_swap(self):

        '''
        Can we replace a device?
        '''

        test_dtb = dtb_objs[tc.to_dtb]
        test_dtb.replace_dev("flash@d0000", "fakeDev@somewhere", {"reg": [0, 1], "foo": "hello"})
        swapped_reg = [x for x in test_dtb.get_node_by_name("fakeDev@somewhere").get_property("reg")]
        swapped_foo = test_dtb.get_node_by_name("fakeDev@somewhere").get_property("foo")[0]
        self.assertEqual([0x0, 0x1], swapped_reg)
        self.assertEqual("hello", swapped_foo)

        # Original is gone, new is present
        self.assertEqual(None, test_dtb.get_node_by_name("flash@d0000"))
        self.assertTrue(isinstance(test_dtb.get_node_by_name("fakeDev@somewhere"), fdt.Node)) # No __eq__

        logging.debug("TEST 3: DTB patching - device swap OK!")

    def test_arch_ID(self):

        '''
        Can we ID architecture?
        '''

        self.assertEqual("arm", dfc.get_arch(dtb_objs[tc.to_dtb]))
        self.assertEqual("powerpc", dfc.get_arch(dtb_objs[tc.gc_dtb]))

        logging.debug("TEST 4: DTB patching - arch ID OK!")

if __name__ == '__main__':
    tc.setup_logging("test_df")
    unittest.main()
