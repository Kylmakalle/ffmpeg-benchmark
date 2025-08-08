# Hetzner FFmpeg Benchmark

## Linux

```shell
apt-get update && apt install ffmpeg -y
```

## macOS

Install [brew](https://brew.sh/)

```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

```shell
brew install ffmpeg
```

```shell
git clone https://github.com/Kylmakalle/ffmpeg-benchmark
cd ffmpeg-benchmark
```

Run the benchmark on cpu and gpu

```shell
python3 main.py
python3 main.py --gpu
```

|   Parallel runs/seconds for full run  |   CCX33 (8/32) (dedicated)  |   CAX41 (16/32) arm  |   CPX51 (16/32)  |   CCX53 (32/128) (dedicated)  |   CCX63 (48/192) (dedicated)  |   VM Xeon v4 (32/32) (dedicated)  |
|---------------------------------------|-----------------------------|----------------------|------------------|-------------------------------|-------------------------------|-----------------------------------|
|   10                                  |   24.5                      |   15                 |   11.6           |   8                           |   5.5                         |   14.8                            |
|   20                                  |   49                        |   28                 |   20.8           |   13.3                        |   10                          |   30                              |
|   30                                  |   73.5                      |   41                 |   30.76          |   19.6                        |   13.7                        |   45                              |
|   40                                  |                             |                      |   40.8           |   26                          |   18                          |   55                              |
|   50                                  |                             |                      |   51.13          |   32.6                        |   22.4                        |   73                              |
|   60                                  |                             |                      |   61.25          |   39                          |   26.87                       |   85                              |
|   70                                  |                             |                      |   71.2           |   45.6                        |   31                          |   97                              |
|   80                                  |                             |                      |                  |   52.1                        |   35.7                        |   109                             |
|   90                                  |                             |                      |                  |   58.7                        |   40.2                        |   120                             |
|   100                                 |                             |                      |                  |   65                          |   44.7                        |   132                             |
|   110                                 |                             |                      |                  |   71.8                        |   49                          |   145                             |
|   120                                 |                             |                      |                  |   78.3                        |   53.5                        |   157                             |
