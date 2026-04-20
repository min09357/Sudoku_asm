
if [[ -z "$1" ]]; then
    echo "No argument !!!"
elif [[ "$1" == "0" ]]; then
    sudo numactl -N 0 -m 0 -C 2 ./reverse_functions -o 1rank -p 20 -t ddr5 -n 1 -s 32 -r 2 -w 8 -d -v -l
elif [[ "$1" == "1" ]]; then
    sudo numactl -N 0 -m 0 -C 3 ./reverse_functions -o 2rank -p 20 -t ddr5 -n 1 -s 32 -r 2 -w 8 -d -v -l
else
    echo "Invalid argument"
fi

