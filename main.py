import argparse
import asyncio
import time
import os
import json
import glob
import platform
import sys


class ShellException(Exception):
    def __init__(
        self,
        message: str = None,
        cmd: str = None,
        stdout: str = None,
        stderr: str = None,
        returncode: int = 1,
    ):
        self.message = message
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(message)

    def __str__(self) -> str:
        return f"ShellException: {self.message or ''}. Exit code: {self.returncode}. Command: {self.cmd or ''}. stderr: {self.stderr or ''}. stdout: {self.stdout or ''}."


async def get_video_info(input_video) -> dict:
    cmd = (
        f"ffprobe -v quiet -print_format json -show_streams -show_format {input_video}"
    )
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(
            f"FFMPEG error get_video_info: stderr: {stderr.decode()}\n stdout: {stdout.decode()}"
        )
    json_data = json.loads(stdout.decode())

    video_info = {
        "width": None,
        "height": None,
        "video_codec": None,
        "audio_codec": None,
        "framerate": None,
        "video_bitrate": None,
        "audio_bitrate": None,
        "duration": None,
    }

    for stream in json_data["streams"]:
        if stream["codec_type"] == "video":
            video_info["width"] = stream["width"]
            video_info["height"] = stream["height"]
            video_info["video_codec"] = stream["codec_name"]
            video_info["framerate"] = stream["avg_frame_rate"]
            video_bitrate = stream.get("bit_rate")
            if video_bitrate:
                video_info["video_bitrate"] = int(video_bitrate)
        elif stream["codec_type"] == "audio":
            video_info["audio_codec"] = stream["codec_name"]
            if video_info["audio_bitrate"]:
                video_info["audio_bitrate"] += int(stream.get("bit_rate", "0"))
            else:
                audio_bitrate = stream.get("bit_rate")
                if audio_bitrate:
                    video_info["audio_bitrate"] = int(audio_bitrate)

    video_info["duration"] = float(json_data["format"]["duration"])
    return video_info


async def shell(
    cmd: str, description: str = None, timeout: int = None, *args, **kwargs
) -> str:
    process = await asyncio.create_subprocess_shell(
        cmd,
        *args,
        **kwargs,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if timeout is not None:
        try:
            await asyncio.wait_for(process.wait(), timeout)
        except asyncio.TimeoutError:
            process.terminate()
            await process.wait()
            raise ShellException(
                f"Timed-out command after {timeout}s. {description or ''}",
                cmd=cmd,
                stderr=process.stderr.decode(),
                stdout=process.stdout.decode(),
                returncode=0,
            )
    else:
        await process.wait()

    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise ShellException(
            message=description,
            cmd=cmd,
            stderr=stderr.decode(),
            stdout=stdout.decode(),
            returncode=process.returncode,
        )
    return stdout.decode() if stdout else stderr.decode()


def check_apple_silicon():
    return platform.system().lower() == "darwin" and platform.machine() == "arm64"


async def check_nvidia_gpu():
    try:
        result = await shell("nvidia-smi", "Checking for NVIDIA GPU", timeout=5)
        return "NVIDIA-SMI" in result
    except Exception:
        return False


async def benchmark(
    input_video: str,
    output_prefix: str,
    dimensions_limit: int,
    size_limit: int,
    num_conversions: int,
    has_nvidia: bool,
    has_apple_silicon: bool,
):
    print(f"Starting {num_conversions} conversions.")
    mp4_files = glob.glob(f"{output_prefix}*.mp4")
    for file in mp4_files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Error: {e.strerror}")

    # Create the directory if it doesn't exist
    os.makedirs(output_prefix, exist_ok=True)
    start = time.time()
    tasks = []

    for i in range(num_conversions):
        output_video = f"{output_prefix}_{i}.mp4"
        task = asyncio.ensure_future(
            convert(
                input_video,
                output_video,
                dimensions_limit,
                size_limit,
                has_nvidia=has_nvidia,
                has_apple_silicon=has_apple_silicon,
            )
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    individual_times = [res[1] for res in results]
    end = time.time()
    print(f"Completed {num_conversions} conversions in {end - start:.2f} seconds.")


async def convert(
    input_video: str,
    output_video: str,
    dimensions_limit: int,
    size_limit: int,
    duration_limit: int = 60,
    bitrate_margin_error_percentage: int = 2,
    recommended_bitrate: int = 2000000,
    timeout: int = None,
    has_nvidia: bool = False,
    has_apple_silicon: bool = False,
) -> str:
    start_time = time.time()
    video_info = await get_video_info(input_video)

    options = []
    duration_option = []

    # Calculate crop dimensions
    if video_info["width"] != video_info["height"]:
        crop_width = min(video_info["width"], video_info["height"])
        crop_height = crop_width
        filters = [f"crop={crop_width}:{crop_height}"]
        if crop_width > dimensions_limit or crop_height > dimensions_limit:
            filters.append(
                f"scale={dimensions_limit}:{dimensions_limit}:flags=fast_bilinear"
            )
        options = ["-vf", ",".join(filters)]
    else:
        # Calculate resize dimensions
        if (
            video_info["width"] > dimensions_limit
            or video_info["height"] > dimensions_limit
        ):
            options = [
                "-vf",
                f"scale={dimensions_limit}:{dimensions_limit}:flags=fast_bilinear",
            ]

    duration = video_info["duration"]
    if duration > duration_limit:
        duration_option = ["-t", str(duration_limit - 1)]
        duration = duration_limit - 1

    # Calculate bitrate
    target_video_bitrate = int(
        size_limit
        * 8
        / 1.048576
        * ((100 - bitrate_margin_error_percentage) / 100)
        / duration
    ) - video_info.get("audio_bitrate", 320)
    bitrate = min(
        video_info.get("video_bitrate", target_video_bitrate),
        target_video_bitrate,
        recommended_bitrate,
    )

    ffmpeg_options = [
        "-preset",
        "p1" if has_nvidia else "superfast",  # p1-p7 for NVENC, lower is faster
        "-sn",
        "-dn",
        *options,
        *duration_option,
        "-b:v",
        str(bitrate),
    ]

    decoder_options = []
    if has_nvidia:
        decoder_options = ["-hwaccel", "cuda", "-c:v", "h264_nvenc"]
        ffmpeg_options = ffmpeg_options + ["-c:v", "h264_nvenc"]
    elif has_apple_silicon:
        decoder_options = ["-hwaccel", "videotoolbox"]
        ffmpeg_options = ffmpeg_options + ["-c:v", "h264_videotoolbox"]

    command = " ".join(
        ["ffmpeg", "-hide_banner", *decoder_options, "-i", input_video]
        + ffmpeg_options
        + [output_video]
    )
    await shell(command, "Resize", timeout=timeout)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Conversion for {output_video} took {elapsed_time:.2f} seconds.")
    return output_video, elapsed_time


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Use GPU acceleration (NVIDIA or Apple Silicon)",
    )
    args = parser.parse_args()

    input_video = "input.mp4"
    dimensions_limit = 384
    size_limit = 8389000

    has_nvidia = False
    has_apple_silicon = False

    if args.gpu:
        print("Requested GPU acceleration.")
        has_nvidia = await check_nvidia_gpu()
        has_apple_silicon = check_apple_silicon()

        if has_nvidia:
            print("✅ NVIDIA GPU detected")
        elif has_apple_silicon:
            print("✅ Apple Silicon detected")
        else:
            print("❌ No supported GPU found. Exiting.")
            sys.exit(1)
    else:
        print("Running without GPU acceleration.")

    for num_conversions in [2, 5, 8, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]:
        await benchmark(
            input_video,
            "output/",
            dimensions_limit,
            size_limit,
            num_conversions,
            has_nvidia,
            has_apple_silicon,
        )


if __name__ == "__main__":
    asyncio.run(main())
