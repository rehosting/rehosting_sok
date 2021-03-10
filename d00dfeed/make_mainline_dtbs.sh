#! /bin/bash

TOGGLE_COLOR='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'

VER_NUM=(5 11 4)
KERNEL="linux-${VER_NUM[0]}.${VER_NUM[1]}.${VER_NUM[2]}"
KERNEL_TAR="$KERNEL.tar.xz"
KERNEL_TAR_URL="https://cdn.kernel.org/pub/linux/kernel/v${VER_NUM[0]}.x/$KERNEL_TAR"
TARGET_DIR="./dtb_data_set"

# Get output dir, if any
if [ ! -z "$1" ] ; then
    if [ ! -d "$1" ] ; then
        echo -e "\n${RED}Invalid output directory: $2 ${TOGGLE_COLOR}"
        exit 1
    else
        TARGET_DIR="$1"
    fi
else
    echo -e "\n${YELLOW}Using default output directory:${TOGGLE_COLOR}\n$(realpath $TARGET_DIR)"
fi

echo -e "\n${YELLOW}Downloading kernel source...${TOGGLE_COLOR}"
wget $KERNEL_TAR_URL -nc -q --show-progress

echo -e "\n${YELLOW}Extracting kernel source...${TOGGLE_COLOR}"

mkdir -p $TARGET_DIR
tar xf  $KERNEL_TAR --checkpoint=.1000 -C $TARGET_DIR
rm $KERNEL_TAR

# Arches chosen for sample size
cd $TARGET_DIR/$KERNEL
echo -e "\n${YELLOW}Building all ARM DTBs...${TOGGLE_COLOR}"
make ARCH=arm allyesconfig dtbs
echo -e "\n${YELLOW}Building all AARCH64 DTBs...${TOGGLE_COLOR}"
make ARCH=arm64 allyesconfig dtbs
echo -e "\n${YELLOW}Building all MIPS DTBs...${TOGGLE_COLOR}"
make ARCH=mips allyesconfig dtbs
echo -e "\n${YELLOW}Building all PPC DTBs...${TOGGLE_COLOR}"
make ARCH=powerpc allyesconfig dtbs

# Final "head count" - 1956 DTBs for paper
DTB_COUNT=$(find . -type f -name *.dtb | wc -l)
echo -e "\n${GREEN}Built $DTB_COUNT DTBs.${TOGGLE_COLOR}"