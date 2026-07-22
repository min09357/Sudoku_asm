
if [[ -z "$1" ]]; then
    echo "No argument !!!"
elif [[ "$1" == "0" ]]; then
    sudo numactl -N 0 -m 0 -C 2 ./identify_bits -o Identify_1 -p 69 -t ddr4 -n 4 -s 32 -r 2 -w 4 -f 0x40,0x100,0x4000,0x80000,0x100000,0x200000,0x1000000040 -d -v -l
    # sudo numactl -N 0 -m 0 -C 2 ./identify_bits -o Identify_1 -p 69 -t ddr4 -n 4 -s 32 -r 2 -w 4 -f 0x40,0x100,0x200,0x8000,0x100000,0x200000,0x400000 -d -v -l
elif [[ "$1" == "1" ]]; then
    sudo numactl -N 1 -m 1 -C 3 ./identify_bits -o Identify_2 -p 24 -t ddr5 -n 1 -s 32 -r 2 -w 4 -f 0x240000,0x82600,0x42120000,0x108404000,0x210808000,0x884042100,0x421090000 -d -v -l
else
    echo "Invalid argument"
fi

