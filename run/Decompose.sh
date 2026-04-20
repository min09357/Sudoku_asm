
if [[ -z "$1" ]]; then
    echo "No argument !!!"
elif [[ "$1" == "0" ]]; then
    sudo numactl -N 0 -m 0 -C 2 ./decompose_functions -o 1rank_1 -p 20 -t ddr5 -n 1 -s 32 -r 2 -w 8 -f 0x240000,0x82600,0x42120000,0x108404000,0x210808000,0x84042100,0x421090000 -R 0x7fff80000 -C 0x1bc0 -d -v -l
elif [[ "$1" == "1" ]]; then
    sudo numactl -N 0 -m 0 -C 3 ./decompose_functions -o 1rank_1 -p 20 -t ddr5 -n 1 -s 32 -r 2 -w 8 -f 0x240000,0x82600,0x42120000,0x108404000,0x210808000,0x84042100,0x421090000 -R 0x7fff80000 -C 0x1bc0 -d -v -l
else
    echo "Invalid argument"
fi
