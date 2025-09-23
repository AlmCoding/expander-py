#!/usr/bin/env python

"""Testing USB communication with tinyframe in a loop"""

from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.EchoCom import EchoCom
from tests.helper import generate_ascii_data
import time


class TestUsbCom:
    LOOP_COUNT = 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 256 + 64

    def test_usb_com_echo(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        usb_com = EchoCom()

        counter = TestUsbCom.LOOP_COUNT
        while counter > 0:
            tx_data = generate_ascii_data(TestUsbCom.DATA_SIZE_MIN, TestUsbCom.DATA_SIZE_MAX)
            usb_com.send(tx_data)
            # print(f"Send: {tx_data}")
            echo = usb_com.read_echo(timeout=0.02)
            assert echo == tx_data
            counter -= 1

        expander.disconnect()

    def test_usb_echo_com_speed(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        usb_com = EchoCom()

        # Generate a list of data to send
        # This is done to avoid generating new data in each loop iteration
        data = []
        counter = TestUsbCom.LOOP_COUNT
        while counter > 0:
            tx_data = generate_ascii_data(TestUsbCom.DATA_SIZE_MAX, TestUsbCom.DATA_SIZE_MAX)
            data.append(tx_data)
            counter -= 1

        start_time = time.time()
        counter = TestUsbCom.LOOP_COUNT
        while counter > 0:
            tx_data = data[counter - 1]
            usb_com.send(tx_data)
            echo = usb_com.read_echo(timeout=0.02)
            assert echo == tx_data
            counter -= 1

        elapsed_time = time.time() - start_time
        total_data_size = sum(len(d) for d in data)
        print(f"Total data size sent: {total_data_size} bytes, in {elapsed_time:.2f} seconds.")
        print(f"Average speed: {total_data_size / elapsed_time:.2f} bytes/second")

        expander.disconnect()
