# Sudoku fork

약간의 코드 수정 및 간단하게 바로 사용할 수 있도록 스크립트 파일을 작성했습니다.

## 1. Environment setup

cpu 노드 당 DIMM을 한 개만 사용 (되도록 DQ를 x4인 DIMM으로)

아래 원본 README.md와 같이 
* alloc hugepage
* fix core/uncore frequency (둘 다 cpu base freq.에 맞춰서. 저는 intel pepc 사용했습니다.)
* disable turbo boost (intel pepc)
* disable prefetch (sudo wrmsr -a 0x1a4 0x2f) 

hugepage의 경우 DIMM 크기의 절반 이상으로 해주세요

    ex) 2소켓 cpu, 각 32GB DIMM 1개씩 -> total huge page=48

pepc 오류 발생 시 grub에  intel_pstate=disable 추가

```bash
GRUB_CMDLINE_LINUX_DEFAULT="iomem=relaxed quiet splash default_hugepagesz=1G hugepagesz=1G hugepages={num-hugepages} intel_pstate=disable"
```

## 2. Build

```bash
cd run
./Build.sh
```

## 3. Run

모두 run 디렉토리에서 진행합니다.

### 3.0 Watch Conflict

latency 분포 확인.

./Conflicts.sh 에서 -p (페이지 개수), -s (DIMM size), -r (rank 개수), -w (DQ)를 맞게 조정한 후

```bash
./Conflicts.sh {node}
# ex) ./Conflicts.sh 0
```

를 하면 Conflicts.stat.single.memory.access.log, Conflicts.stat.paired.memory.access.log 파일이 만들어지는데 해당 파일을 보내주시면

./sudoku/internal/intel_gnr.h 의 파라미터를 업데이트하겠습니다.

### 3.1 Reverse-engineering (DRAMA)

./Reverse.sh 를 아래 원본 README를 참고해서 맞게 수정해주세요.

```bash
./Reverse.sh {node}
# ex) ./Reverse.sh 0
```

파라미터를 올바르게 설정하면 아래와 같은 출력이 나옵니다.

```bash
./Reverse.sh 0
[+] Collect Same Bank, Different Row Pairs
Insert address 0x4661a59c0 to set 0. <== NEW!!
Insert address 0x4e5872d00 to set 1. <== NEW!!
Insert address 0x3a859cf80 to set 0 with latency 630 cycles. Set size: 1, num Sets: 2
Insert address 0x57f3ad8c0 to set 2. <== NEW!!
Insert address 0x370fe2d40 to set 3. <== NEW!!

(생략)

Found functions:
  0x240000    bits: 18,21 
  0x82600    bits: 9,10,13,19 
  0x42120000    bits: 17,20,25,30 
  0x108404000    bits: 14,22,27,32 
  0x210808000    bits: 15,23,28,33 
  0x421090000    bits: 16,19,24,29,34 
  0x884042100    bits: 8,13,18,26,31,35 
```

만약 출력에 set의 개수가 DIMM의 뱅크 개수(ddr5 2랭크 기준 128) 보다 훨씬 적거나 많은 상태로 Insert address가 오래 이어진다면 파라미터 설정을 잘못한 것이고, 코드가 끝나지 않을 가능성이 높으니 중단하고 알려주세요.

### 3.2 Identify row and column bits

./Identify.sh 를 마찬가지로 수정해주세요.

-f 에는 위에서 나온 function을 나열하면 됩니다.

```bash
./Identify.sh {node}
# ex) ./Identify.sh 0

(생략)

Found bits: 
  row_bits,0x3fffc0000, bits: 18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33
  column_bits,0xfc0, bits: 6,7,8,9,10,11 
```

다만, Sapphire Rapids의 경우 page policy가 strict closed로 추정되어 row hit이 불가능해 이 단계는 항상 실패했습니다.

Grand Ridge도 마찬가지일 것으로 추정되니 만약 여기서 실패한다면 알려주세요.

### 3.3 Validating DRAM address mapping

./Validate.sh 를 마찬가지로 수정해주세요.

-R 은 row bits, -C는 column bits 입니다.

위에서 얻은 function들이 GF(2)에 잘 매핑되는지 확인하는 단계입니다.

위의 단계들을 통과했다면 웬만해선 성공합니다.

```bash
./Validate.sh {node}
# ex) ./Validate.sh 0
```

### 3.4 Decomposing DRAM address mapping into component functions

./Decompose.sh 를 마찬가지로 수정해주세요.

```bash
./Decompose.sh {node}
# ex) ./Decompose.sh 0

(생략)

[+] Check refresh intervals of function 0x81100
Functions: 0x81100, tREFI: 932, tREFI/2: 92
[+] Check refresh intervals of function 0x42300
Functions: 0x42300, tREFI: 946, tREFI/2: 78
[+] Check refresh intervals of function 0x44420000
Functions: 0x44420000, tREFI: 1, tREFI/2: 1023
[+] Check refresh intervals of function 0x88844000
Functions: 0x88844000, tREFI: 1020, tREFI/2: 4
[+] Check refresh intervals of function 0x111108000
Functions: 0x111108000, tREFI: 1023, tREFI/2: 1
[+] Check refresh intervals of function 0x222210000
Functions: 0x222210000, tREFI: 1006, tREFI/2: 18
[2026-02-11 05:48:56.711] [info] [+] DecomposeUsingConsecutiveAccesses
[+] Check consecutive memory accesses of function 0x81100
Functions: 0x81100, Avg RDRD latency: 428
[+] Check consecutive memory accesses of function 0x42300
Functions: 0x42300, Avg RDRD latency: 428
[+] Check consecutive memory accesses of function 0x44420000
Functions: 0x44420000, Avg RDRD latency: 474
[+] Check consecutive memory accesses of function 0x88844000
Functions: 0x88844000, Avg RDRD latency: 417
[+] Check consecutive memory accesses of function 0x111108000
Functions: 0x111108000, Avg RDRD latency: 416
[+] Check consecutive memory accesses of function 0x222210000
Functions: 0x222210000, Avg RDRD latency: 469
```


아래는 원본 README 입니다.


# Sudoku: Decomposing DRAM Address Mapping into Component Functions

**Sudoku** is a software-based tool for decomposing DRAM address mapping into component functions. 
Sudoku runs on Linux and supports Intel Core and AMD Ryzen processors with both DDR4 and DDR5 DRAMs.

We have tested Sudoku on the following systems:
| Processor                                       | Microcode | Motherboard  | Tested DDR                |
| ----------------------------------------------- | --------- | ------------ | ------------------------- |
| Intel Core i9-12900K (12th Alder Lake)          | 0x38      | ASUS Z690-A  | 32GB DDR4-3200 2Rx8 UDIMM |
| Intel Core i9-12900K (12th Alder Lake)          | 0x38      | ASUS Z690-F  | 32GB DDR4-3200 2Rx8 UDIMM |
| Intel Core i9-14900K (14th Raptor Lake Refresh) | 0x12C     | MSI B760M    | 32GB DDR5-4800 2Rx8 UDIMM |
| AMD Ryzen 9 7950X (Zen 4)                       | 0xA601206 | ASRock X670E | 32GB DDR5-4800 2Rx8 UDIMM |

Sudoku provides the following key features:
* [reverse_functions](./sudoku/reverse_functions.cc): Reverse-engineering DRAM addressing functions using row buffer conflicts (refer to [DRAMA](https://github.com/isec-tugraz/drama))
* [identify_bits](./sudoku/identify_bits.cc): Identifying DRAM row and column bits from given DRAM addressing functions using row buffer conflicts
* [validate_mapping](./sudoku/validate_mapping.cc): Validating DRAM address mapping by checking system's injectivity
* [decompose_functions](./sudoku/decompose_functions.cc): Decomposing DRAM address mapping into component functions

Also, for get statistics of paired memory accesses, auto-refreshes, and consecutive memory accesses, Sudoku provides the following testing binaries:
* [watch_conflicts](./sudoku/testing/watch_conflicts.cc)
* [watch_refreshes](./sudoku/testing/watch_refreshes.cc)
* [watch_consecutive_accesses](./sudoku/testing/watch_consecutive_accesses.cc)

## Environment setup

Sudoku requires large memory coverage via **1 GB hugepages**. 
Suggested hugepage count is over half of the system memory (to consider MSB bits of system's physical address).
We enable the desired number of hugepages as follows:

```bash
# Change the grub file
sudo vi /etc/default/grub
GRUB_CMDLINE_LINUX_DEFAULT="iomem=relaxed quiet splash default_hugepagesz=1G hugepagesz=1G hugepages={num-hugepages}"

# Update grub
sudo update-grub

# Reboot the system to enable modified grub setting
sudo reboot
```

Sudoku measure timings using \texttt{RDTSC} instruction, requiring fixed core frequency for measurement accuracy. 
We fix the processor's frequency to base clock frequency using cpupower.

```bash
sudo cpupower frequency-set -d 3.2GHz
sudo cpupower frequency-set -u 3.2GHz
```

Or, you can disable processor's DVFS in the BIOS.

## Build Sudoku

Sudoku requires precise timing threshold for correct functionality. 
We provide tested constants through header files. 
Please pass the correct compiler flag to link the correct constants.

```bash
vi CMakeLists.txt
# Please modify the below option.
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -D{DESIRED_ARCH_WITH_DDR_TYPE}")
# Supported flag:
#   -DCOMPILE_ALDER_LAKE_DDR4
#   -DCOMPILE_ALDER_LAKE_DDR5
#   -DCOMPILE_RAPTOR_LAKE
#   -DCOMPILE_ZEN_4_DDR5

mkdir -p build && cd build
cmake ..
cmake --build . --parallel
```

## Use Sudoku
### (Optional) Reverse-engineering DRAM addressing functions

Sudoku provides the code for reverse-engineering DRAM addressing functions. 
We employ [DRAMA](https://github.com/isec-tugraz/drama)'s brute-forcing method.

```bash
sudo numactl -C {core} -m {memory} ./reverse_addressing 
    -o {fname_prefix} -p {num_pages} -t {ddr_type} -n {num_dimms} \
    -s {dimm_size} -r {num_ranks} -w {dq_width} -d -v -l
```

### Identifying DRAM row and column bits

```bash
sudo numactl -C {core} -m {memory} ./identify_bits 
    -o {fname_prefix} -p {num_pages} -t {ddr_type} -n {num_dimms} \
    -s {dimm_size} -r {num_ranks} -w {dq_width} \
    -f {functions_separated_by_commas} \
    -d -v -l
```

### Validating DRAM address mapping

```bash
sudo numactl -C {core} -m {memory} ./validate_mapping
    -o {fname_prefix} -p {num_pages} -t {ddr_type} -n {num_dimms} \
    -s {dimm_size} -r {num_ranks} -w {dq_width} \
    -f {functions_separated_by_commas} \
    -R {row_bits} -C {column_bits} \
    -d -v -l
```

### Decomposing DRAM address mapping into component functions

```bash
sudo numactl -C {core} -m {memory} ./decompose_functions
    -o {fname_prefix} -p {num_pages} -t {ddr_type} -n {num_dimms} \
    -s {dimm_size} -r {num_ranks} -w {dq_width} \
    -f {functions_separated_by_commas} \
    -R {row_bits} -C {column_bits} \
    -d -v -l
```

## License

This project is licensed under the MIT License (see [LICENSE](./LICENSE)).

## Contact

Please open an issue if you have questions or issues!

Minbok Wi (minbok.wi@scale.snu.ac.kr or homakaka@snu.ac.kr)
