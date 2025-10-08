from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.DigitalToAnalog import DigitalToAnalog, DAC_MAX_SAMPLE_BUFFER_SPACE, DAC_MAX_SAMPLE_VALUE
import math
import time
import random


class TestDigitalToAnalog:
    REQUEST_COUNT = 100
    SAMPLING_RATE = 22000

    def test_set_voltage(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        dac = DigitalToAnalog()
        for _ in range(TestDigitalToAnalog.REQUEST_COUNT):
            dac.set_voltage(ch0=4.2, ch1=0.0)
            dac.set_voltage(ch0=0.0, ch1=4.2)
            dac.set_voltage(ch0=12, ch1=-12)
            dac.set_voltage(ch0=6.9)
            dac.set_voltage(ch1=-6.9)
        expander.disconnect()

    def test_loop_sequence(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        dac = DigitalToAnalog()

        for _ in range(TestDigitalToAnalog.REQUEST_COUNT):
            sample_count = random.randint(2, DAC_MAX_SAMPLE_BUFFER_SPACE)
            sin_sequence = [
                int((math.sin(i * 2 * math.pi / sample_count) + 1) / 2 * DAC_MAX_SAMPLE_VALUE)
                for i in range(sample_count)
            ]
            jigsaw_sequence = [int(i / (sample_count - 1) * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)]

            dac.loop_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
            )
        expander.disconnect()

    def test_stream_sequence(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        dac = DigitalToAnalog()

        sample_count = DAC_MAX_SAMPLE_BUFFER_SPACE + 42
        sin_sequence = [
            int((math.sin(i * 2 * math.pi / sample_count) + 1) / 2 * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)
        ]
        jigsaw_sequence = [int(i / (sample_count - 1) * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)]

        for _ in range(TestDigitalToAnalog.REQUEST_COUNT):
            dac.stream_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
            )
            assert not dac.buffer_underrun_ch0
            assert not dac.buffer_underrun_ch1

        time.sleep(1)
        dac._wait_for_all_responses(0.1)
        assert dac.buffer_underrun_ch0
        assert dac.buffer_underrun_ch1
        expander.disconnect()

    def test_output_loop_stream_transitions(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        dac = DigitalToAnalog()

        sample_count = 512
        sin_sequence = [
            int((math.sin(i * 2 * math.pi / sample_count) + 1) / 2 * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)
        ]
        jigsaw_sequence = [int(i / (sample_count - 1) * DAC_MAX_SAMPLE_VALUE) for i in range(sample_count)]

        for _ in range(TestDigitalToAnalog.REQUEST_COUNT):
            dac.set_voltage(ch0=4.242, ch1=0.0)
            dac.set_voltage(ch0=0.0, ch1=4.242)
            dac.set_voltage(ch0=12.005, ch1=-12.005)

            dac.loop_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
            )

            dac.set_voltage(ch0=4.242, ch1=0.0)
            dac.set_voltage(ch0=0.0, ch1=4.242)
            dac.set_voltage(ch0=12.005, ch1=-12.005)

            # time.sleep(0.1)
            for i in range(5):
                dac.stream_sequence(
                    sequence_ch0=sin_sequence,
                    sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                    sequence_ch1=jigsaw_sequence,
                    sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
                )
            # time.sleep(0.05)

            dac.set_voltage(ch0=4.242, ch1=0.0)
            dac.set_voltage(ch0=0.0, ch1=4.242)
            dac.set_voltage(ch0=12.005, ch1=-12.005)

            dac.loop_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
            )

            for i in range(5):
                dac.stream_sequence(
                    sequence_ch0=sin_sequence,
                    sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                    sequence_ch1=jigsaw_sequence,
                    sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
                )

            dac.loop_sequence(
                sequence_ch0=sin_sequence,
                sampling_rate_ch0=TestDigitalToAnalog.SAMPLING_RATE,
                sequence_ch1=jigsaw_sequence,
                sampling_rate_ch1=TestDigitalToAnalog.SAMPLING_RATE,
            )

        expander.disconnect()
