#! /bin/bash

# Init
set -ue
cd $(dirname "$0")

# For coloring important terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NORMAL='\033[0m'

# Dirs
ANALYSES_DIR="../analyses"

# Test files
df="test_df"
qemu="test_qemu"

# Mypy config
type_check_cmd=(
    mypy
    --python-version 3.6
    --ignore-missing-imports    # TODO: eventually use real module management to fix this
)

# Collected Py files for type checking
# TODO: add type annoations to all files!
typed_files=()
typed_files+=("../df.py")
typed_files+=("../df_common.py")
typed_files+=("../df_analyze.py")
while IFS= read -r line; do
    typed_files+=("$line")
done < <(find $ANALYSES_DIR -type f -name "*.py")

# Run python unit test and view logs
run_test() {

    echo -e "\n${YELLOW}Running $1:${NORMAL}\n"
    python3 ./$1.py
    echo -e "\n${YELLOW}Log from $1 (TEST lines only):${NORMAL}\n"
    cat $1.log | grep "TEST"

}

# Typing check
echo -e "\n${YELLOW}Running typechecking...${NORMAL}\n"
for file_path in "${typed_files[@]}"
do
    eval "${type_check_cmd[@]} $file_path"
    ret_code=$?
    if [ "$ret_code" -eq 0 ]; then
        echo -e "${GREEN}TYPING OK: $(basename $file_path)${NORMAL}"
    else
        echo -e "${RED}TYPE CHECK FAILED: $(basename $file_path)${NORMAL}"
    fi
done

# Unit tests
run_test $df
run_test $qemu