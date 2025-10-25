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

    dac.set_current(ch0=24, ch1=-24)  # Channel 0 to 24mA, Channel 1 to -24mA
    dac.set_current(ch0=4.2)  # Channel 0 to 4.2mA, Channel 1 unchanged
    dac.set_current(ch1=6.9)  # Channel 1 to 6.9mA, Channel 0 unchanged

    # generate current waveforms
    sin = get_sin_waveform(amplitude=24.0, sample_count=1024)
    saw = get_jigsaw_waveform(amplitude=6.0, sample_count=420)

    sin = [DigitalToAnalog.current_to_voltage(i) for i in sin]
    saw = [DigitalToAnalog.current_to_voltage(i) for i in saw]

    # stream waveforms on both channels
    dac.stream_sequence(
        sequence_ch0=sin,
        sampling_rate_ch0=16000,
        sequence_ch1=saw,
        sampling_rate_ch1=4000,
    )
    # for this mode the max sampling rate is 20 kS/s
    # sampling rates can differ from each other but one must be an integer multiple of the other
