from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.DigitalToAnalog import DigitalToAnalog
from pydub import AudioSegment
from typing import Iterator, Tuple, List
import numpy as np





def _load_and_resample_mp3(path: str, target_sr: int, sample_width: int = 2) -> AudioSegment:
    seg = AudioSegment.from_file(path, format="mp3")
    seg = seg.set_frame_rate(target_sr)
    seg = seg.set_sample_width(sample_width)
    return seg


def _segment_to_float_channels(seg: AudioSegment, amplitude: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert AudioSegment to two float arrays (left, right) with range ±amplitude.
    """
    raw = seg.raw_data
    sw = seg.sample_width
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[sw]
    arr = np.frombuffer(raw, dtype=dtype)

    # Normalize to -1.0 .. +1.0
    max_val = float(np.iinfo(dtype).max)
    norm = arr.astype(np.float32) / max_val

    if seg.channels == 1:
        left = norm
        right = norm
    elif seg.channels == 2:
        left = norm[0::2]
        right = norm[1::2]
    else:
        stereo = seg.set_channels(2)
        return _segment_to_float_channels(stereo, amplitude)

    # Scale to desired amplitude
    left *= amplitude
    right *= amplitude

    return left, right


def get_channel_generator_from_mp3(
    path: str,
    amplitude: float = 1.0,
    sampling_rate: int = 20000,
    block_size_bytes: int = 1024,
) -> Tuple[Iterator[List[float]], Iterator[List[float]]]:
    """
    Returns two generators yielding float voltage samples in blocks.
    Each block corresponds to block_size_bytes of original PCM data
    (e.g., 512 samples for 16-bit mono, 256 per channel for stereo).

    Example: amplitude=1.2 → output values between ±1.2 V
    """
    seg = _load_and_resample_mp3(path, sampling_rate)
    left, right = _segment_to_float_channels(seg, amplitude)

    # Calculate how many samples per block (for 16-bit PCM, 2 bytes per sample)
    samples_per_block = block_size_bytes // 2

    def gen_from_array(arr: np.ndarray) -> Iterator[List[float]]:
        total = len(arr)
        pos = 0
        while pos < total:
            block = arr[pos : pos + samples_per_block]
            if len(block) < samples_per_block:
                # pad with zeros (silence)
                block = np.pad(block, (0, samples_per_block - len(block)))
            yield block.tolist()
            pos += samples_per_block

    return gen_from_array(left), gen_from_array(right)


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()
    dac = DigitalToAnalog()

    mp3_file = r"test.mp3"
    sampling_rate = 10000

    # create generators from mp3 file
    left_gen, right_gen = get_channel_generator_from_mp3(
        mp3_file, amplitude=1.2, sampling_rate=sampling_rate, block_size_bytes=2048
    )

    while True:
        try:
            left = next(left_gen)
            right = next(right_gen)
        except StopIteration:
            break

        # stream waveforms on both channels
        dac.stream_sequence(
            sequence_ch0=left,
            sampling_rate_ch0=sampling_rate,
            sequence_ch1=right,
            sampling_rate_ch1=sampling_rate,
        )
        # for this mode the max sampling rate is 20 kS/s
        # sampling rates can differ from each other but one must be an integer multiple of the other
