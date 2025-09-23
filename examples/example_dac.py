from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.DigitalToAnalog import DigitalToAnalog, DAC_MAX_SAMPLE_BUFFER_SPACE, DAC_MAX_SAMPLE_VALUE
import math
import time


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    dac = DigitalToAnalog()

    sampling_rate = 24000
    sample_count = 512
    sin_sequence = [
        int((math.sin(i * 2 * math.pi / sample_count) + 1) / 2 * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)
    ]
    jigsaw_sequence = [int(i / (sample_count - 1) * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)]

    for _ in range(690):
        dac.output_voltage(voltage_ch0=4.242, voltage_ch1=0.0)
        dac.output_voltage(voltage_ch0=0.0, voltage_ch1=4.242)
        dac.output_voltage(voltage_ch0=12.005, voltage_ch1=-12.005)

        dac.loop_sequence(
            sequence_ch0=sin_sequence,
            sampling_rate_ch0=sampling_rate,
            sequence_ch1=jigsaw_sequence,
            sampling_rate_ch1=sampling_rate,
        )

        dac.output_voltage(voltage_ch0=4.242, voltage_ch1=0.0)
        dac.output_voltage(voltage_ch0=0.0, voltage_ch1=4.242)
        dac.output_voltage(voltage_ch0=12.005, voltage_ch1=-12.005)

        # time.sleep(0.1)
        for i in range(69):
            dac.stream_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=sampling_rate,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=sampling_rate,
            )
        # time.sleep(0.05)

        dac.output_voltage(voltage_ch0=4.242, voltage_ch1=0.0)
        dac.output_voltage(voltage_ch0=0.0, voltage_ch1=4.242)
        dac.output_voltage(voltage_ch0=12.005, voltage_ch1=-12.005)


        dac.loop_sequence(
            sequence_ch0=sin_sequence,
            sampling_rate_ch0=sampling_rate,
            sequence_ch1=jigsaw_sequence,
            sampling_rate_ch1=sampling_rate,
        )

        for i in range(69):
            dac.stream_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=sampling_rate,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=sampling_rate,
            )

        dac.loop_sequence(
            sequence_ch0=sin_sequence,
            sampling_rate_ch0=sampling_rate,
            sequence_ch1=jigsaw_sequence,
            sampling_rate_ch1=sampling_rate,
        )

    expander.disconnect()
