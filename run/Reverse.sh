
if [[ -z "$1" ]]; then
    echo "No argument !!!"
elif [[ "$1" == "0" ]]; then
    sudo numactl -N 0 -m 0 -C 2 ./reverse_functions -o Reverse_1 -p 69 -t ddr4 -n 4 -s 32 -r 2 -w 4 -d -v -l
elif [[ "$1" == "1" ]]; then
    sudo numactl -N 1 -m 1 -C 3 ./reverse_functions -o Reverse_2 -p 24 -t ddr5 -n 1 -s 32 -r 2 -w 4 -d -v -l
else
    echo "Invalid argument"
fi



# Found functions:
#   0x40    bits: 6 
#   0x100    bits: 8 
#   0x4000    bits: 14 
#   0x80000    bits: 19 
#   0x100000    bits: 20 
#   0x200000    bits: 21 
#   0x1000000040    bits: 6,36