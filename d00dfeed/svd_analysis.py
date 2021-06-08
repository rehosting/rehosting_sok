#!/usr/bin/env python3

import os
import pickle
import statistics
from peewee import *
from cmsis_svd.parser import SVDParser
from pathlib import Path
from strsimpy.normalized_levenshtein import NormalizedLevenshtein

#import logging
#logger = logging.getLogger('peewee')
#logger.addHandler(logging.StreamHandler())
#logger.setLevel(logging.DEBUG)

db = SqliteDatabase('svd.db')

class BaseModel(Model):
    class Meta:
        database = db

class Vendor(BaseModel):
    name = CharField(unique=True)
    # SoCs <-
    def __str__(self):
        return f"Vendor {self.name}"

class SoC(BaseModel): # One SoC for each name/vendor combo (backed by SVD file). Multiple SoCs per vendor
    name = TextField()
    vendor = ForeignKeyField(Vendor, backref='SoCs')
    # peripherals <-
    def __str__(self):
        return f"SoC: {self.name} by {self.vendor}"

class Peripheral(BaseModel): # Each SoC has many peripherals. Multiple SoCs *may* reference the same peripheral
    size = IntegerField()
    # registers <- Registers
    # interrupts <- Interrupts
    # names <-PeripheralNames
    # SoCs <-PeripheralSocs

    def shortname(self): # Like str but without SoCs list
        names = ", ".join([x.name for x in self.names.select()])
        return f"{len(self.registers): >4}R \t 0x{self.size:>4x}S \t 0x{len(self.interrupts):>3x}I \t [{names}]"

    def __str__(self):
        names = ", ".join([x.name for x in self.names.select()])
        socs = ", ".join([x.soc.name+f"({x.occurances})" for x in self.SoCs.select()])
        interrupts = "No interrupts"
        if len(self.interrupts):
            interrupts = f"interrupts: ({', '.join([hex(x.value) for x in self.interrupts])})"
        return f"[{names}] {len(self.registers)} registers, size={self.size}. "\
               f"{interrupts}. Present in {socs}"

class PeripheralSoC(BaseModel): # for many-many SoC-Peripheral
    peripheral = ForeignKeyField(Peripheral, backref='SoCs')
    soc = ForeignKeyField(SoC, backref='peripherals')
    occurances = IntegerField()

    def __str__(self):
        pnames = [x.name for x in self.peripheral.names.select()]
        return f"Relation between {pnames} and {self.soc}"

class PeripheralName(BaseModel): # 1 peripheral may have many names (note duplicates are allowed for different peripherals)
    name = CharField()
    peripheral = ForeignKeyField(Peripheral, backref='names')

class Interrupt(BaseModel):
    value = IntegerField() # Single address and size
    peripheral = ForeignKeyField(Peripheral, backref='interrupts') # A peripheral has many interrupts

class Register(BaseModel):
    # names <-RegNames
    addr = IntegerField() # Single address and size
    size = IntegerField(128)
    peripheral = ForeignKeyField(Peripheral, backref='registers') # A peripheral has many registers

class RegName(BaseModel): # 1 Register may have many names (note duplicates are allowed for different registers)
    name = TextField()
    register = ForeignKeyField(Register, backref='names') # Many names
    def __str__(self):
        return f"Register name: {self.name}"

def duplicate_peripherals(new, old):
    """
    Determine if two peripherals could be the same by:
        - Close enough names, AND
        - Interrupts are the same
        - Sizes are the same
        - Sizes of all sub-registers are the same
    Don't actually combine them
    """

    # First check to ensure new name is close enough to at least one existing name for this peripheral
    existing_names = [x.name for x in old.names.select()]
    new_name = new.name
    normalized_lev = NormalizedLevenshtein()
    name_match = False
    for existing_name in existing_names:
        if new_name and existing_name: # Both not-none
            if normalized_lev.distance(new_name, existing_name) <= 0.25:
                name_match = True
                break
        elif not new_name and not existing_name: # Both none
                name_match = True
                break

    if not name_match: # Names sufficiently different, bail
        return False

    # Check interrupts
    old_interrupt_c = old.interrupts.count()
    if new.interrupts is None:
        if old_interrupt_c != 0:
            return False
    else:
        if len(new.interrupts) != old_interrupt_c:
            return False

    if old_interrupt_c > 0:
        old_interrupts = [x.value for x in old.interrupts.select()]
        for new_int in [x.value for x in new.interrupts]:
            if new_int not in old_interrupts:
                return False

    # Now check register offsets
    old_offsets = {}
    new_offsets = {}

    for new_reg in new.registers:
        new_offsets[new_reg.address_offset] = new_reg.size

    for old_reg in old.registers.select():
        old_offsets[old_reg.addr] = old_reg.size

    # Three easy cases to consider
    # different number of registers
    if len(old_offsets.keys()) != len(new_offsets.keys()):
        return False

    # Alternatively- if set(old_reg.keys()) != set(new_reg.keys()): return False
    # In the existing device, there's a register that isn't in the new device
    for k in old_offsets.keys():
        if k not in new_offsets.keys():
            return False

    # In the new device, there's a register that isn't in the existing device
    for k in new_offsets.keys():
        if k not in old_offsets.keys():
            return False

    for k in old_offsets.keys(): # keys are identical
        if old_offsets[k] != new_offsets[k]:
            return False

    """ # Example for getting names from an existing peripheral registers
    for old_reg, new_reg in zip(old.registers, new.registers.select()):
        print("\tOLD: "+old_reg.name, old_reg.address_offset, old_reg.size)
        new_names = []
        for x in new_reg.names.select(): # 
            new_names.append(x.name)
        print("\tNEW:"+str(new_names), new_reg.addr, new_reg.size)
    """

    return True

def analyze_peripheral(peripheral, soc):
    # Determine if a new peripheral object should be created for this peripheral
    # If so, create Registers and Peripheral

    # Key idea: if it's a duplicate of an existing peripheral, we just need to maybe add new
    #           RegNames and PeripheralNames. But if it's an entirely new Peripheral, we need
    #           to also create the Peripheral

    # Initially, this peripheral could be equivalent to anything in our DB - Filter down to valid matches
    potential_peripherals = []
    existing_peripherals = Peripheral.select()
    for potential_duplicate in existing_peripherals:
        if duplicate_peripherals(peripheral, potential_duplicate):
            potential_peripherals.append(potential_duplicate)

    # No valid matches - it's a new peripheral
    if not len(potential_peripherals):
        # Create Peripheral object
        sz = sum([x.size for x in peripheral.registers if x.size]) # May be none?
        p = Peripheral.create(SoC=soc, size=sz)
        PeripheralName.create(name=peripheral.name, peripheral=p)

        # Add relation between Peripheral and SoCs
        PeripheralSoC.create(peripheral=p, soc=soc, occurances=1)

        # Also create (new) interrupts
        if peripheral.interrupts is not None:
            for val in [x.value for x in peripheral.interrupts]:
                i = Interrupt.create(value=val, peripheral=p)

        # Also create (new) registers
        if peripheral.registers is not None:
            for reg in peripheral.registers:
                r = Register.create(addr=reg.address_offset, size=reg.size, peripheral=p)
                RegName.create(name=reg.name, register=r)

    # Multiple valid matches - Need to select the best match
    elif len(potential_peripherals) > 1:
        # Find the peripheral name with the lowest normalized Leven. - Could also do per-register name?
        normalized_lev = NormalizedLevenshtein()
        best_lev, best_p = (1, None)

        print("HAVE MULTIPLE POTENTIAL PERIPHS:")
        for p in potential_peripherals:
            print(p)

        for p in potential_peripherals: # For each existing potential, consider the closest name to what we have
            existing_names = [x.name for x in p.names.select()]
            for existing_name in existing_names:
                this_delta = normalized_lev.distance(peripheral.name, existing_name)
                if this_delta  < best_lev:
                    best_lev = this_delta
                    best_p = p

        assert(best_p is not None) # Must select the best
        potential_peripherals = [p]
    
    if len(potential_peripherals): # Just have one- now make it happen
        assert(len(potential_peripherals) == 1) # Must have been filtered if there were many
        # New instance of an old peripheral

        p = potential_peripherals[0]

        # Update mapping to SoC - Either increment occurances or add new relation
        periph_soc_mapping = PeripheralSoC.select().where(PeripheralSoC.soc == soc, PeripheralSoC.peripheral ==p)
        if periph_soc_mapping.count() > 0:
            # Exists already, update occurances
            rel = periph_soc_mapping.get()
            occ = rel.occurances
            PeripheralSoC.update(occurances=(occ+1)).where(PeripheralSoC.peripheral==p & 
                                        PeripheralSoC.soc == soc).execute()
        else:
            # New (Peripheral, SoC) pair. Create relationship with occurances initialized to 1
            PeripheralSoC.create(peripheral=p, soc=soc, occurances=1)

        # Add new name if necessary
        (_, new_p) = PeripheralName.get_or_create(name=peripheral.name, peripheral=p)

        if new_p: # If we see a new name, print the new name
            print(f"New instance of ({p}): {peripheral.name}")

        # Also create new register names for each field in the peripheral, as necessary
        for reg in p.registers.select():
            existing_names = [x.name for x in reg.names.select()]
            #print(existing_names, "at ", reg.addr)
            # Find name of new peripheral register at the offset
            for new_peripheral_reg in peripheral.registers:
                if new_peripheral_reg.address_offset == reg.addr:
                    if new_peripheral_reg.name not in existing_names: # New name at this address - Update RegName
                        RegName.create(name=new_peripheral_reg.name, register=reg)
                    break # Only one peripheral at each address

def analyze_files(svd_files):
    for f in svd_files:
        parser = SVDParser.for_xml_file(f)
        device = parser.get_device()

        # Get (and create if needed) vendor
        vendor_name = f.parts[-2]
        (vendor, is_new_vendor) = Vendor.get_or_create(name=vendor_name)

        # Have we already analysed this SoC? if so skip it
        soc_name = f.parts[-1].replace("_SVD.svd","").replace(".svd", "")
        if is_new_vendor:
            analyzed = False
        else:
            analyzed = SoC.select().where(SoC.name==soc_name, SoC.vendor==vendor).count() > 0
        if analyzed:
            print("Already analyzed:", soc_name)
            continue
        else:
            print("Analyzing:", vendor_name, soc_name)

        soc = SoC.create(name=soc_name, vendor=vendor)
        for peripheral in device.peripherals:
            analyze_peripheral(peripheral, soc)

        #with open(cache_file, "wb") as f:
        #    pickle.dump(periph_count, f)

def present_results():
    # Use global DB to print results
    """
    data = {} # Vendor_name: [nperiphs1, nperiphs2...]

    for v in Vendor.select():
        socs = v.SoCs.select()
        #print(f"Vendor: {v.name} has {len(socs)} analyzed SoCs")
        data[v.name] = {'nperiphs': [], # List of number of peripherals for each SoC
                        'pids': set(),  # Set of all peripheral IDs observed on SoCs of this vendor
                        'nsoc': len(socs)}

        # Populate data
        for s in socs:
            nperiphs = len([x for x in s.peripherals])
            data[v.name]['nperiphs'].append(nperiphs)

            for s_p in s.peripherals:
                data[v.name]['pids'].add(s_p.peripheral.id)

    # Generate Table 3: Peripheral Diversity in Cortex-M Systems
    with open("table3.tex", "w") as f:
        for vendor in sorted(data):
            detail = data[vendor]
            n = detail['nsoc']
            if n < 10:
                continue

            nperiphs = detail['nperiphs']
            unique_p = len(detail['pids'])
            f.write("\\textbf{{{vendor: <16}}} &      {n: <3}    & {unique_p: <3}  &   {mean: <3.0f} $\pm$ {stdev: <3.0f}    &  {median: <3.0f} \\\\\n".format(
                vendor=vendor, n=n, unique_p=unique_p, nperiphs=nperiphs, mean=statistics.mean(nperiphs),
                stdev=statistics.stdev(nperiphs), median=statistics.median(nperiphs)))
    """

    # View by peripheral - Which are in multiple vendors?
    overlap_counts = {}
    for p in Peripheral.select():
        socs = p.SoCs.select()
        vendors = set([ps.soc.vendor.name for ps in socs])
        tv = tuple(vendors)
        if tv not in overlap_counts.keys():
            overlap_counts[tv] = 0
        overlap_counts[tv] +=1

        if len(vendors) > 2:
            print(p.shortname(), "\t in ", " ".join(vendors))

    for vendors in sorted(overlap_counts, key=lambda x: overlap_counts[x]):
        count = overlap_counts[vendors]
        print("{} peripherals in [{}]".format(count, ' '.join(vendors)))

    # Overlapping peripheral results - Mostly Fujitsu and Spansion, and some Freescale and NXP
    """
    1 peripherals in [STMicro Freescale]
    1 peripherals in [STMicro NXP]
    1 peripherals in [STMicro Holtek]
    2 peripherals in [STMicro NXP Freescale]
    96 peripherals in [Freescale NXP]
    2 peripherals in [Freescale Atmel NXP]
    1 peripherals in [Freescale Atmel]
    1 peripherals in [TexasInstruments Toshiba]
    221 peripherals in [Fujitsu Spansion]
    """

def monte(vendor, reps=8, n=None):
    # Run a monte carlo simulation of modeling peripherals from `vendor`
    # Select `n` SoCs (if n==None, select half), repeat `reps` times

    # Populate data
    v = Vendor.select().where(Vendor.name==vendor).get()
    if n is None:
        n = int(v.SoCs.select().count()/2)

    sims = {} # round -> [list of P_u values we had at that round]
    for rep_idx in range(reps): # This will run once for each time we repeat (rep)
        socs = v.SoCs.select().order_by(fn.Random()).limit(n)
        modeled = {} # PeriphName: RoundModeled
        for round_idx, s in enumerate(socs): # This will run N times
            if round_idx not in sims:
                sims[round_idx] =[]
            unmod_round_ctr = 0
            already_mod_round_ctr = 0
            for p_s in s.peripherals:
                p = p_s.peripheral
                if p not in modeled:
                    modeled[p] = round_idx
                    unmod_round_ctr+=1
                else:
                    already_mod_round_ctr+=1
            sims[round_idx].append(unmod_round_ctr) # Store how many peripherals we just had to model

            #print(f"\tAt end of round {round_idx}, have {len(modeled)} peripherals modeled.")
            #print(f"\tThis round modeled {unmod_round_ctr} new peripherals and used {already_mod_round_ctr} already modeled")
        #print(f"Iteration {rep_idx}: modeling peripherals for {n} systems requires building {len(modeled)} models")

    # Need to write output file as follows: with idx at the start of each line, then the results from each simulation
    # 0 [res1[0]] [res2[0]]...
    # 1 [res1[1]] [res2[1] ...
    #with open(f"svd_unimp_per_rehost_{vendor}.dat", "w") as f: # From monte_carlo_sim.py's write_dict_of_list_data_file
    #    for k, v in sims.items():
    #        f.write(str(k) + ' ' + ' '.join(str(e) for e in v) + "\n")

    with open(f"svd_unimp_per_rehost_{vendor}.csv", "w") as f:
        f.write("idx, mean, stdev\n")
        for k, v in sims.items():
            f.write(f"{k}, {round(statistics.mean(v))}, {round(statistics.stdev(v))}\n")

def monte_all(reps=8, n=None):
    # Run a monte carlo simulation of modeling peripherals from all vendors
    # Select `n` SoCs (if n==None, select half), repeat `reps` times

    # Populate data
    sims = {} # round -> [list of P_u values we had at that round]
    for rep_idx in range(reps): # This will run once for each time we repeat (rep)
        socs = SoC.select().order_by(fn.Random()).limit(n)
        modeled = {} # PeriphName: RoundModeled
        for round_idx, s in enumerate(socs): # This will run N times
            if round_idx not in sims:
                sims[round_idx] =[]
            unmod_round_ctr = 0
            already_mod_round_ctr = 0
            for p_s in s.peripherals:
                p = p_s.peripheral
                if p not in modeled:
                    modeled[p] = round_idx
                    unmod_round_ctr+=1
                else:
                    already_mod_round_ctr+=1
            sims[round_idx].append(unmod_round_ctr) # Store how many peripherals we just had to model

            #print(f"\tAt end of round {round_idx}, have {len(modeled)} peripherals modeled.")
            #print(f"\tThis round modeled {unmod_round_ctr} new peripherals and used {already_mod_round_ctr} already modeled")
        #print(f"Iteration {rep_idx}: modeling peripherals for {n} systems requires building {len(modeled)} models")

    # Need to write output file as follows: with idx at the start of each line, then the results from each simulation
    # 0 [res1[0]] [res2[0]]...
    # 1 [res1[1]] [res2[1] ...
    #with open(f"svd_unimp_per_rehost_{vendor}.dat", "w") as f: # From monte_carlo_sim.py's write_dict_of_list_data_file
    #    for k, v in sims.items():
    #        f.write(str(k) + ' ' + ' '.join(str(e) for e in v) + "\n")

    with open(f"svd_unimp_per_rehost_all.csv", "w") as f:
        f.write("idx, mean, stdev\n")
        for k, v in sims.items():
            f.write(f"{k}, {round(statistics.mean(v))}, {round(statistics.stdev(v))}\n")

def count_unique_p():
    periphs = set()
    for vend in Vendor.select():
        if vend.SoCs.select().count() <10:
            print(f"Skipping {vend}")
            continue

        for s in vend.SoCs.select():
            for p_s in s.peripherals.select():
                periphs.add(p_s.peripheral)
    print(f"Across vendors with n>=10, have a total of {len(periphs)} distinct periphs")


if __name__ == "__main__":
    db.connect()

    db.create_tables([PeripheralName, Peripheral, PeripheralSoC])
    db.create_tables([Vendor, SoC,  RegName, Register, Interrupt])

    debug = False
    if debug:
        # Debugging - just use one vendor, STM
        svd_files = Path("cmsis-svd/data/STMicro").glob("**/*.svd") # XXX: Only STM files
    else:
        # All inputs
        svd_files = Path("cmsis-svd/data/").glob("**/*.svd")

    analyze_files(svd_files)
    present_results()

    print("\nRunning monte carlo simulation")
    if debug:
        monte("STMicro", 1000) # Has 1077 unique periphs
    if not debug:
        monte_all(1000, 100)

    db.close()
