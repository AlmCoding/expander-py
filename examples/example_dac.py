import time

from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.DigitalToAnalog import DigitalToAnalog, DAC_MAX_SAMPLE_BUFFER_SPACE, DAC_MAX_SAMPLE_VALUE
import matplotlib.pyplot as plt
import math

if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    dac = DigitalToAnalog()

    """
    dac.output_voltage(voltage_ch0=0.0, voltage_ch1=0.0)
    dac.output_voltage(voltage_ch0=11, voltage_ch1=11)
    dac.output_voltage(voltage_ch0=5, voltage_ch1=5)
    dac.output_voltage(voltage_ch0=1, voltage_ch1=1)

    dac.output_voltage(voltage_ch0=-11, voltage_ch1=-11)
    dac.output_voltage(voltage_ch0=-5, voltage_ch1=-5)
    dac.output_voltage(voltage_ch0=-1, voltage_ch1=-1)

    dac.output_voltage(voltage_ch0=11, voltage_ch1=-11)
    dac.output_voltage(voltage_ch0=-11, voltage_ch1=11)
    dac.output_voltage(voltage_ch0=5, voltage_ch1=-5)
    dac.output_voltage(voltage_ch0=-5, voltage_ch1=5)
    dac.output_voltage(voltage_ch0=1, voltage_ch1=-1)
    dac.output_voltage(voltage_ch0=-1, voltage_ch1=1)

    dac.output_voltage(voltage_ch0=1, voltage_ch1=11)
    dac.output_voltage(voltage_ch0=11, voltage_ch1=1)
    dac.output_voltage(voltage_ch0=-1, voltage_ch1=-11)
    dac.output_voltage(voltage_ch0=-11, voltage_ch1=-1)
    """

    sample_count = 512  # DAC_MAX_SAMPLE_BUFFER_SPACE
    sin_sequence = [
        int((math.sin(i * 2 * math.pi / sample_count) + 1) / 2 * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)
    ]
    jigsaw_sequence = [int(i / (sample_count - 1) * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)]

    for i in range(10000):
        dac.stream_sequence(
            sequence_ch0=sin_sequence,
            sampling_rate_ch0=50000,
            sequence_ch1=jigsaw_sequence,
            sampling_rate_ch1=50000,
        )
        # time.sleep(1)

    dac.loop_sequence(
        sequence_ch0=sin_sequence,
        sampling_rate_ch0=200000,
        sequence_ch1=jigsaw_sequence,
        sampling_rate_ch1=200000,
    )

    dac.output_voltage(voltage_ch0=0.0, voltage_ch1=0.0)
    dac.output_voltage(voltage_ch0=10, voltage_ch1=10)
    dac.output_voltage(voltage_ch0=-10, voltage_ch1=-10)

    dac.output_value(value_ch0=DAC_MAX_SAMPLE_VALUE // 10, value_ch1=DAC_MAX_SAMPLE_VALUE // 10)

    dac.output_value(value_ch0=DAC_MAX_SAMPLE_VALUE, value_ch1=None)
    dac.output_value(value_ch0=None, value_ch1=0)
    dac.output_value(value_ch0=DAC_MAX_SAMPLE_VALUE // 2, value_ch1=DAC_MAX_SAMPLE_VALUE // 2)
    dac.output_value(value_ch0=0, value_ch1=0)
    dac.output_value(value_ch0=DAC_MAX_SAMPLE_VALUE, value_ch1=DAC_MAX_SAMPLE_VALUE)

    # dac.loop_sequence(sequence_ch1=[1,2,3,4,5,6,7], sequence_ch2=[1,2,3,4,5,6,7], sampling_rate=1000)

    # sample_count = 424 # DAC_MAX_SAMPLE_BUFFER_SPACE
    # sin_sequence = [int((math.sin(i * 2 * math.pi / sample_count) + 1) / 2 * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)]
    """
    # Plot the sequence
    plt.figure(figsize=(12, 6))
    plt.plot(sin_sequence, 'b.-')
    plt.title('Generated Sine Wave Sequence')
    plt.xlabel('Sample Number')
    plt.ylabel('DAC Value')
    plt.grid(True)
    plt.axhline(y=DAC_MAX_SAMPLE_VALUE/2, color='r', linestyle='--', label='Midpoint')
    plt.legend()
    plt.show()
    """

    # dac.loop_sequence(sequence_ch1=sin_sequence, sequence_ch2=sin_sequence, sampling_rate=1000)

    expander.disconnect()
