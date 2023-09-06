# Hetzner FFmpeg Benchmark

```shell
apt-get update && apt install ffmpeg -y
git clone https://github.com/Kylmakalle/ffmpeg-benchmark
cd ffmpeg-benchmark
python3 main.py
```

|   Parallel runs/seconds for full run  |   CCX33 (8/32) (dedicated)  |   CAX41 (16/32) arm  |   CPX51 (16/32)  |   CCX63 (48/192) (dedicated)  |
|---------------------------------------|-----------------------------|----------------------|------------------|-------------------------------|
|   10                                  |   24.5                      |   15                 |   11.6           |   5.5                         |
|   20                                  |   49                        |   28                 |   20.8           |   10                          |
|   30                                  |   73.5                      |   41                 |   30.76          |   13.7                        |
|   40                                  |                             |                      |   40.8           |   18                          |
|   50                                  |                             |                      |   51.13          |   22.4                        |
|   60                                  |                             |                      |   61.25          |   26.87                       |
|   70                                  |                             |                      |   71.2           |   31                          |
|   80                                  |                             |                      |                  |   35.7                        |
|   90                                  |                             |                      |                  |   40.2                        |
|   100                                 |                             |                      |                  |   44.7                        |
|   110                                 |                             |                      |                  |   49                          |
|   120                                 |                             |                      |                  |   53.5                        |
