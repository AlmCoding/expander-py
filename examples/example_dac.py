from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.DigitalToAnalog import DigitalToAnalog
import math


def get_sin_waveform(amplitude: float, sample_count: int) -> list[float]:
    return [amplitude * math.sin(i * 2 * math.pi / sample_count) for i in range(sample_count)]


def get_jigsaw_waveform(amplitude: float, sample_count: int) -> list[float]:
    return [amplitude + 2 * amplitude * i / (sample_count - 1) for i in range(sample_count)]


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()
    dac = DigitalToAnalog()

    dac.set_voltage(ch0=12, ch1=-12)  # Channel 0 to 12V, Channel 1 to -12V
    dac.set_voltage(ch0=0.42)  # Channel 0 to 0.42V, Channel 1 unchanged
    dac.set_voltage(ch1=0.69)  # Channel 1 to 0.69V, Channel 0 unchanged

    # generate waveforms
    sin = get_sin_waveform(amplitude=12.0, sample_count=1024)
    saw = get_jigsaw_waveform(amplitude=6.0, sample_count=420)

    # periodic waveforms on both channels
    dac.loop_sequence(
        sequence_ch0=sin,
        sampling_rate_ch0=20000,
        sequence_ch1=saw,
        sampling_rate_ch1=4000,
    )
    # for this mode the max sampling rate is 200 kS/s
    # sampling rates can differ from each other but one must be an integer multiple of the other
