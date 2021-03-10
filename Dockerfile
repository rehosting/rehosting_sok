FROM ubuntu:20.04

# Asset import
RUN mkdir -p /rehosting_sok
RUN mkdir -p /rehosting_sok/d00dfeed
COPY ./d00dfeed /rehosting_sok/d00dfeed

# Build tools: DTBs and QEMU
ENV TZ=US/New_York
RUN apt-get update -y
RUN DEBIAN_FRONTEND="noninteractive" apt-get install -y \
    tzdata \
    wget \
    git \
    fakeroot \
    build-essential \
    ninja-build \
    ncurses-dev \
    xz-utils \
    libssl-dev \
    bc \
    flex \
    libelf-dev \
    bison \
    device-tree-compiler \
    libglib2.0-dev \
    libfdt-dev \
    libpixman-1-dev \
    zlib1g-dev \
    python3 \
    python3-pip \
    python3-setuptools

# Python deps
RUN python3 -m pip install --upgrade setuptools wheel pip
RUN python3 -m pip install -r /rehosting_sok/d00dfeed/requirements.txt

# Build DTBs
WORKDIR /rehosting_sok/d00dfeed
RUN bash ./make_mainline_dtbs.sh

# Build QEMU 5.2.0
WORKDIR /tmp
RUN git clone https://github.com/qemu/qemu.git
WORKDIR /tmp/qemu
RUN git submodule init
RUN git submodule update --recursive
RUN git submodule status --recursive
RUN git checkout v5.2.0
RUN mkdir build
WORKDIR /tmp/qemu/build
RUN ../configure
RUN make install -j$(nproc)
RUN which qemu-system-arm
RUN which qemu-system-aarch64
RUN which qemu-system-mips
RUN which qemu-system-i386
RUN which qemu-system-x86_64

# Run basic tests to ensure container is functional
RUN /rehosting_sok/d00dfeed/test/run_tests.sh

# Compute DTB summaries
WORKDIR /rehosting_sok/d00dfeed
RUN python3 df_analyze.py ./dtb_data_set --linux-src-dir --output-dir ./dtb_json_stats