# Rehosting SoK Repeatable Experiments

This repository contains code allowing anyone to replicate the empirical backbone of our AsiaCCS 2021 paper, `SoK: Enabling Security Analyses of Embedded Systems via Rehosting`.

Prior firmware measurement studies used web crawlers to collect publicly available firmware images.
These approaches are difficult to reproduce as copyright restrictions prevent corpora distribution and link rot prevents crawlers from running successfully after paper release.
By contrast, our experiments are fully containerized and fully reproducible.

To build the container:

```
docker build -t rehosting_sok .
```

To connect to the container:

```
docker run --rm -it rehosting_sok
```

## Replicates the Paper's DTB Results

At creation time, the container will build 1956 DTBs from source, run unit tests to verify DTB processing logic is functional, and compute JSON summaries for every DTB.
You are ready to replicate paper results.
The below steps will print the raw metrics to the terminal, to see the generated graphs (PNG images) you'll need to setup X11 forwarding to the Docker container (outside the scope of this tutorial).

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

Device driver columns:

```
cd /rehosting_sok/d00dfeed/analyses
python3 graph_dd_sloc_by_arch.py ../dtb_json_stats/
```

SoC columns:

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

## Replicates the Paper's SVD Results

TODO: Andrew add equivalent instruction here, Tiemoko hasn't looked at the SVD code.

## Citation BibTex

TODO: Add here
