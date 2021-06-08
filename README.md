# Rehosting SoK Repeatable Experiments

This repository contains code allowing anyone to replicate the empirical backbone of our AsiaCCS 2021 paper, `SoK: Enabling Security Analyses of Embedded Systems via Rehosting`.

Prior firmware measurement studies used web crawlers to collect publicly available firmware images.
These approaches are difficult to reproduce as copyright restrictions prevent corpora distribution and link rot prevents crawlers from running successfully after paper release.
By contrast, our experiments are fully containerized and fully reproducible.

To start the container:
```sh

user@host$ git clone git@github.com:rehosting/rehosting_sok.git
user@host$ docker build -t rehosting_sok .
user@host$ docker run --rm -it rehosting_sok
root@container#
```

## Replicate the Paper's DTB Results

At creation time, the container will build 1956 DTBs from source, run unit tests to verify DTB processing logic is functional, and compute JSON summaries for every DTB.
You are ready to replicate paper results.
The below steps will print the raw metrics to the terminal, to see the generated graphs (PNG images) you'll need to setup X11 forwarding to the Docker container or change the scripts to write the graphs to disk in a shared folder (outside the scope of this tutorial).

### Replicating Table 1 (Observed CPU models supported by QEMU versions)

```
cd /rehosting_sok/d00dfeed/analyses
python3 graph_qemu_supported_cpus.py ../dtb_json_stats/
```

### Replicating Table 2A (Peripheral diversity, Type-1 Linux Systems (DTB corpus))

SoC count column:

```
cd /rehosting_sok/d00dfeed/analyses
python3 graph_dtbs_by_arch.py ../dtb_json_stats/
```

Peripheral columns:

```
cd /rehosting_sok/d00dfeed/analyses
python3 graph_peripherals_by_arch.py ../dtb_json_stats/
```

### Replicating Table 3 (SLOC for open-source device drivers)

Both device driver columns:

```
cd /rehosting_sok/d00dfeed/analyses
python3 graph_dd_sloc_by_arch.py ../dtb_json_stats/
```

SoC SLOC column (count column comes from table 2A):

```
cd /rehosting_sok/d00dfeed/analyses
python3 print_sloc_per_soc.py ../dtb_json_stats/
```

### Running the DTB Monte Carlo Simulation

Run simulation to produce `.dat` files (used for paper's graphs):

```
cd /rehosting_sok/d00dfeed/analyses/monte_carlo_sim
python3 monte_carlo_sim.py ../../dtb_json_stats --rehost-cnt 195 --iter-cnt 1000 --no-qemu
```

Note the simulation may take several hours to complete.
Use `python3 monte_carlo_sim.py --help` for more options.

Compute aggregate stats:

```
cd /rehosting_sok/d00dfeed/analyses/monte_carlo_sim
python3 dat_metrics.py
```

## Replicate the Paper's SVD Results
The SVD analysis builds off the [posborne/cmsis-svd](https://github.com/posborne/cmsis-svd) repo. As that repository is updated with additional SVD files, the results will change slightly.

### Generate SVD data
```
root@container# cd /rehosting_sok/d00dfeed
root@container# python3 svd_periph_count.py
root@container# python3 svd_analysis.py
```

### Analyze SVD data
The script `svd_periph_count` will print the number of total peripherals described in the SVD corpus and calculate statistics per silicon vendor.

The script `svd_analysis.py` will populate the SQLite database `svd.db` with information on each SoC and peripheral. The script will also store the result of the Monte Carlo simulation in a file name `svd_unimp_per_rehost_all.csv`.

## Citation BibTex
```
@inproceedings{fasano2021sok,
  title={{SoK}: Enabling Security Analyses of Embedded Systems via Rehosting},
  author={Fasano, Andrew and Ballo, Tiemoko and Muench, Marius and Leek, Tim and Bulekov, Alexander and Dolan-Gavitt, Brendan and Egele, Manuel and Francillon, Aurelien and Lu, Long and Gregory, Nick and others},
  booktitle={ACM ASIA Conference on Computer and Communications Security (ASIACCS)},
  url = {https://dspace.mit.edu/handle/1721.1/130505},
  year={2021}
}
```
