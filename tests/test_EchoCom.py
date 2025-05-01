#!/usr/bin/env python

""" Testing USB communication with tinyframe in a loop
"""

from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.EchoCom import EchoCom
from tests.helper import generate_ascii_data


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
            print(f"Send: {tx_data}")
            echo = usb_com.read_echo(timeout=0.02)
            assert echo == tx_data
            counter -= 1

        expander.disconnect()
