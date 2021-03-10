#! /usr/bin/python3

import os, sys, unittest, logging, timeit, random, fdt
import test_common as tc

sys.path.append('../')   # TODO: there's probably a pythonic way to relative import
import df
import df_common as dfc

class test_dtb(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def test_qemu_machine_getters(self):

        arm_machines = dfc.get_qemu_machines(dfc.ARCH_TO_QEMU_BIN['arm'])
        self.assertTrue('vexpress-a15' in arm_machines)
        self.assertTrue('vexpress-a9' in arm_machines)
        self.assertTrue('virt' in arm_machines)
        self.assertTrue('none' in arm_machines)

        arm64_machines = dfc.get_qemu_machines(dfc.ARCH_TO_QEMU_BIN['arm64'])
        self.assertTrue('vexpress-a15' in arm64_machines)
        self.assertTrue('vexpress-a9' in arm64_machines)
        self.assertTrue('virt' in arm64_machines)
        self.assertTrue('none' in arm64_machines)

        microblaze_machines = dfc.get_qemu_machines(dfc.ARCH_TO_QEMU_BIN['microblaze'])
        self.assertTrue('petalogix-ml605' in microblaze_machines)
        self.assertTrue('none' in microblaze_machines)

        mips_machines = dfc.get_qemu_machines(dfc.ARCH_TO_QEMU_BIN['mips'])
        self.assertTrue('malta' in mips_machines)
        self.assertTrue('none' in mips_machines)

        ppc_machines = dfc.get_qemu_machines(dfc.ARCH_TO_QEMU_BIN['ppc'])
        self.assertTrue('bamboo' in ppc_machines)
        self.assertTrue('none' in ppc_machines)

        logging.debug("TEST 1: QEMU machines names getter OK!")

    def test_qemu_cpu_getters(self):

        arm_cpus = dfc.get_qemu_cpus(dfc.ARCH_TO_QEMU_BIN['arm'], "virt")
        self.assertTrue('arm926' in arm_cpus)
        self.assertTrue('cortex-m4' in arm_cpus)

        arm64_cpus = dfc.get_qemu_cpus(dfc.ARCH_TO_QEMU_BIN['arm64'], "virt")
        self.assertTrue('cortex-a57' in arm64_cpus)
        self.assertTrue('cortex-a53' in arm64_cpus)

        # Ignoring microblaze...

        mips_cpus = dfc.get_qemu_cpus(dfc.ARCH_TO_QEMU_BIN['mips'], "malta")
        self.assertTrue('P5600' in mips_cpus)
        self.assertTrue('4Kc' in mips_cpus)

        ppc_cpus = dfc.get_qemu_cpus(dfc.ARCH_TO_QEMU_BIN['ppc'], "bamboo")
        self.assertTrue('mpc8540' in ppc_cpus)
        self.assertTrue('e500' in ppc_cpus)

        logging.debug("TEST 2: QEMU CPU names getter OK!")

    def test_qemu_device_getters(self):

        arm_devs = dfc.get_qemu_devices(dfc.ARCH_TO_QEMU_BIN['arm'], "virt")
        #self.assertTrue('armv7m_nvic' in arm_devs) # Why not present in newer QEMU?
        self.assertTrue('nand' in arm_devs)

        arm64_devs = dfc.get_qemu_devices(dfc.ARCH_TO_QEMU_BIN['arm64'], "virt")
        #self.assertTrue('exynos4210.i2c' in arm64_devs) # Why not present in newer QEMU?
        self.assertTrue('nand' in arm_devs)
        self.assertTrue('lm8323' in arm_devs)

        mips_devs = dfc.get_qemu_devices(dfc.ARCH_TO_QEMU_BIN['mips'], "malta")
        self.assertTrue('cs4231a' in mips_devs)

        ppc_devs = dfc.get_qemu_devices(dfc.ARCH_TO_QEMU_BIN['ppc'], "bamboo")
        self.assertTrue('isa-m48t59' in ppc_devs)

        logging.debug("TEST 3: QEMU devices names getter OK!")

    def test_qemu_multi_board_getter(self):

        all_arm_cpus = dfc.get_all_qemu_strs_by_arch('arm', get_cpus=True, get_devs=False)
        all_arm_cpus_devs = dfc.get_all_qemu_strs_by_arch('arm', get_cpus=True, get_devs=True)
        self.assertTrue((len(all_arm_cpus) > 0) and (len(all_arm_cpus_devs) > 0))
        self.assertTrue(len(all_arm_cpus) < len(all_arm_cpus_devs))

        all_arm64_cpus = dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=True, get_devs=False)
        all_arm64_cpus_devs = dfc.get_all_qemu_strs_by_arch('arm64', get_cpus=True, get_devs=True)
        self.assertTrue((len(all_arm64_cpus) > 0) and (len(all_arm64_cpus_devs) > 0))
        self.assertTrue(len(all_arm64_cpus) < len(all_arm64_cpus_devs))

        all_mips_cpus = dfc.get_all_qemu_strs_by_arch('mips', get_cpus=True, get_devs=False)
        all_mips_cpus_devs = dfc.get_all_qemu_strs_by_arch('mips', get_cpus=True, get_devs=True)
        self.assertTrue((len(all_mips_cpus) > 0) and (len(all_mips_cpus_devs) > 0))
        self.assertTrue(len(all_mips_cpus) < len(all_mips_cpus_devs))

        all_ppc_cpus = dfc.get_all_qemu_strs_by_arch('ppc', get_cpus=True, get_devs=False)
        all_ppc_cpus_devs = dfc.get_all_qemu_strs_by_arch('ppc', get_cpus=True, get_devs=True)
        self.assertTrue((len(all_ppc_cpus) > 0) and (len(all_ppc_cpus_devs) > 0))
        self.assertTrue(len(all_ppc_cpus) < len(all_ppc_cpus_devs))

        logging.debug("TEST 4: QEMU multi board getter OK!")

if __name__ == '__main__':
    tc.setup_logging("test_qemu")
    unittest.main()
