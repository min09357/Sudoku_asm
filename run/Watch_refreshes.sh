
#!/bin/bash
set -e

# 1. 인자 개수 처리
if [ "$#" -eq 1 ]; then
    NODE_ID=$1
    MODE="stat"
elif [ "$#" -eq 2 ]; then
    NODE_ID=$1
    MODE=$2
else
    echo "Usage: $0 <node_id> <mode>"
    exit 1
fi

EXTRA_ARGS=""

if [[ "$NODE_ID" == "0" ]]; then
# 0x40,0x100,0x4000,0x80000,0x100000,0x200000,0x1000000040
    SAME="0x40,0x100,0x4000,0x80000,0x100000,0x200000"
    DIFF="0x1000000000"

    ROW="0xfffc70000"
    COL="0xbe80"
elif [[ "$NODE_ID" == "1" ]]; then
    SAME="0x40,0x8000080,0x10000100,0x80000200,0x20000400,0x40000800"
    DIFF=""

    ROW="0x7fff80000"
    COL="0x7f000"
else
    echo "Invalid argument"
fi


if [[ "$MODE" == "check" ]]; then
    EXTRA_ARGS="-S $SAME -D $DIFF -R $ROW -C $COL"
fi



if [[ "$NODE_ID" == "0" ]]; then
    sudo numactl -N $NODE_ID -m $NODE_ID  ./watch_refreshes -o refreshes -p 75 -m $MODE -t ddr4 -n 4 -s 32 -r 2 -w 4 -d -v -l $EXTRA_ARGS
elif [[ "$NODE_ID" == "1" ]]; then
    sudo numactl -N $NODE_ID -m $NODE_ID  ./watch_refreshes -o refreshes -p 24 -m $MODE -t ddr5 -n 1 -s 32 -r 1 -w 4 -d -v -l $EXTRA_ARGS
else
    echo "Invalid argument"
fi



