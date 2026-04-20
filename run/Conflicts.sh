
if [[ -z "$1" ]]; then
    echo "No argument !!!"
elif [[ "$1" == "0" ]]; then
    sudo numactl -N 0 -m 0 -C 2 ./watch_conflicts -o Conflicts_1 -p 24 -m stat -t ddr5 -n 1 -s 32 -r 2 -w 4 -S -D -R -C -d -v -l
elif [[ "$1" == "1" ]]; then
    sudo numactl -N 1 -m 1 -C 3 ./watch_conflicts -o Conflicts_2 -p 24 -m stat -t ddr5 -n 1 -s 32 -r 2 -w 4 -S -D -R -C -d -v -l
else
    echo "Invalid argument"
fi


