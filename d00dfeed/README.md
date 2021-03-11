## Analysis of DTB file(s)

Analysis is a 3 stage pipeline:

1. Download Linux kernel and build all DTBs (ARM, AARCH64, MIPS, PPC).
2. Parse features of interest to JSON, in parallel.
3. Process JSONs to answer a particular question, graph and/or print results.

Steps 1 and 2 are done for you during container build.
See this repo's [main README](../README.md) for examples of step 3.

## Tests

Run tests with:

```
./test/run_tests.sh
```

## Author

Tiemoko Ballo
