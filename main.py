import asyncio
import time
import subprocess
import os
import json


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
                stderr=process.stderr,
                stdout=process.stdout,
                returncode=0,
            )
    else:
        await process.wait()
    if process.returncode != 0:
        raise Exception(
            message=description,
            cmd=cmd,
            stderr=process.stderr,
            stdout=process.stdout,
            returncode=process.returncode,
        )
    return process.stdout or process.stderr


async def benchmark(
    input_video: str,
    output_prefix: str,
    dimensions_limit: int,
    size_limit: int,
    num_conversions: int,
):
    print(
        f"Starting {num_conversions} conversions.",
    )
    await shell(f"rm -rf {output_prefix}*.mp4", "")
    await shell(f"mkdir -p {output_prefix}", "")
    start = time.time()
    tasks = []

    for i in range(num_conversions):
        output_video = f"{output_prefix}_{i}.mp4"
        task = asyncio.ensure_future(
            convert(
                input_video, output_video, dimensions_limit, size_limit
            )
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    individual_times = [res[1] for res in results]
    # print(f"Individual Conversion Times: {individual_times}")

    end = time.time()
    print(f"Completed {num_conversions} conversions in {end - start} seconds.")


async def convert(
    input_video: str,
    output_video: str,
    dimensions_limit: int,
    size_limit: int,
    duration_limit: int = 60,
    bitrate_margin_error_percentage: int = 2,
    recommended_bitrate: int = 2000000,
    timeout: int = None,
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
        "superfast",
        "-sn",
        "-dn",
        *options,
        *duration_option,
        "-b:v",
        str(bitrate),
    ]

    await shell(
        " ".join(
            ["ffmpeg", "-hide_banner", "-i", input_video]
            + ffmpeg_options
            + [output_video]
        ),
        "Resize",
        timeout=timeout,
    )
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Conversion for {output_video} took {elapsed_time:.2f} seconds.")
    return output_video, elapsed_time


async def main():
    # Assume test_video.mp4 exists in the cloned repo.
    input_video = "input.mp4" # "heavy_video.mp4"
    dimensions_limit = 384
    size_limit = 8389000
    for num_conversions in [10, 20, 30]:
        await benchmark(
            input_video, "output/", dimensions_limit, size_limit, num_conversions
        )


if __name__ == "__main__":
    asyncio.run(main())
