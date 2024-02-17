#!/usr/bin/env python

""" Testing Gpio write/notify
"""

import pytest
import serial
from msg import tiny_frame
from msg import proto_gpio_msg as pm
from helper import get_com_port


@pytest.fixture()
def serial_port():
    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        yield ser


class TestGpio:
    REQUEST_COUNT = 1000

    def setup_class(self):
        self.reverse = False
        self.counter = 0
        self.patter_counter = 0

    @staticmethod
    def config_gpio(reverse: bool):
        if reverse:
            pm.GpioInterface.send_config_msg([
                pm.GpioConfig(pm.GpioId.GPIO0, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO1, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO2, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO3, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO4, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO5, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO6, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO7, pm.GpioMode.INPUT_PULLDOWN),
            ])
        else:
            pm.GpioInterface.send_config_msg([
                pm.GpioConfig(pm.GpioId.GPIO0, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO1, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO2, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO3, pm.GpioMode.INPUT_PULLDOWN),
                pm.GpioConfig(pm.GpioId.GPIO4, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO5, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO6, pm.GpioMode.OUTPUT_PUSHPULL),
                pm.GpioConfig(pm.GpioId.GPIO7, pm.GpioMode.OUTPUT_PUSHPULL),
            ])

    def generate_pattern(self):
        # Convert the number to its binary representation
        binary = bin(self.patter_counter)[2:]
        # Pad the binary representation with leading zeros if necessary
        binary = binary.zfill(pm.GpioId.GPIO_CNT.value // 2)
        # Create a list of booleans representing the bits
        bool_list = [bit == '1' for bit in binary]

        self.patter_counter += 1
        if self.patter_counter > (pow(2, pm.GpioId.GPIO_CNT.value / 2) - 1):
            self.patter_counter = 0

        print("Send pattern ({}): {}".format(self.counter, bool_list))
        return list(reversed(bool_list))

    def send_pattern(self):
        if self.counter == TestGpio.REQUEST_COUNT // 2:
            self.config_gpio(True)

        pattern = self.generate_pattern()
        data = []

        for gpio_id, mode in pm.GpioInterface.Config.items():
            if mode == pm.GpioMode.OUTPUT_PUSHPULL or \
                    mode == pm.GpioMode.OUTPUT_OPENDRAIN:
                data.append(pm.OutputData(gpio_id, pattern[0]))
                pattern = pattern[1:]

        pm.GpioInterface.send_data_msg(data)
        self.counter += 1

    def verify_pattern(self):
        if pm.GpioInterface.InputData[pm.GpioId.GPIO0] == pm.GpioInterface.InputData[pm.GpioId.GPIO4] and \
                pm.GpioInterface.InputData[pm.GpioId.GPIO1] == pm.GpioInterface.InputData[pm.GpioId.GPIO5] and \
                pm.GpioInterface.InputData[pm.GpioId.GPIO2] == pm.GpioInterface.InputData[pm.GpioId.GPIO6] and \
                pm.GpioInterface.InputData[pm.GpioId.GPIO3] == pm.GpioInterface.InputData[pm.GpioId.GPIO7]:
            return
        pytest.fail("Gpio pattern mismatch (count: %d, data: %s)" % (self.counter, pm.GpioInterface.InputData.values()))

    def test_gpio_write_notify(self, serial_port):
        tf = tiny_frame.tf_init(serial_port.write)

        TestGpio.config_gpio(False)
        self.send_pattern()

        while True:
            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            if pm.GpioInterface.Synchronized:
                self.verify_pattern()
                if self.counter < TestGpio.REQUEST_COUNT:
                    self.send_pattern()
                else:
                    break



