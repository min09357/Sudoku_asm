
if [[ -z "$1" ]]; then
    echo "No argument !!!"
elif [[ "$1" == "0" ]]; then
    sudo numactl -N 0 -m 0 -C 2 ./reverse_functions -o Reverse_1 -p 24 -t ddr5 -n 1 -s 32 -r 2 -w 4 -d -v -l
elif [[ "$1" == "1" ]]; then
    sudo numactl -N 1 -m 1 -C 3 ./reverse_functions -o Reverse_2 -p 24 -t ddr5 -n 1 -s 32 -r 2 -w 4 -d -v -l
else
    echo "Invalid argument"
fi

