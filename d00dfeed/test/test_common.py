import logging, os

# Test files
dtb_dir = "dtbs"
to_dtb = os.path.join(dtb_dir, "turris_omnia.dtb")
gc_dtb = os.path.join(dtb_dir, "gamecube.dtb")
dtb_test_files = {
    to_dtb,
    gc_dtb
}

# Timing iterations
TIMING_ITER = 1000

# Logger
def setup_logging(test_name):
    logging.basicConfig(
        level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        filename=(test_name + '.log'),
                        filemode='w')

# Timing wrapper
def timing_wrapper(func, *args, **kwargs):
    def wrapped():
        return func(*args, **kwargs)
    return wrapped
