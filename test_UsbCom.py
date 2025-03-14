#!/usr/bin/env python

""" Testing USB communication with tinyframe in a loop
"""

from msg import tiny_frame
from helper import serial_port, generate_ascii_data

RX_DATA = None


def tiny_frame_receive_cb(_, tf_msg):
    global RX_DATA
    if isinstance(tf_msg, tiny_frame.TF.TF_Msg):
        RX_DATA = tf_msg.data
    else:
        rx_data = RX_DATA
        RX_DATA = None
        return rx_data


class TestUsbCom:
    LOOP_COUNT = 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 256 + 64

    def test_usb_tinyframe_loop(self, serial_port):
        tf = tiny_frame.tf_init(serial_port.write)
        tiny_frame.tf_register_callback(tiny_frame.TfMsgType.TYPE_ECHO, tiny_frame_receive_cb)

        # TestUsbCom.DATA_SIZE_MAX -= tiny_frame.TF_FRAME_OVERHEAD_SIZE
        counter = TestUsbCom.LOOP_COUNT
        while counter > 0:
            tx_data = generate_ascii_data(TestUsbCom.DATA_SIZE_MIN, TestUsbCom.DATA_SIZE_MAX)
            tf.send(tiny_frame.TfMsgType.TYPE_ECHO.value, tx_data, 0)
            # Wait for the response
            while True:
                if serial_port.in_waiting > 0:
                    # Read the incoming data
                    rx_data = serial_port.read(serial_port.in_waiting)
                    tf.accept(rx_data)
                    tf_rx_data = tiny_frame_receive_cb(None, None)
                    if tf_rx_data is None:
                        continue
                    else:
                        assert tf_rx_data == tx_data
                        counter -= 1
                        break

    """
    def test_usb_tinyframe_loop_stress(self, serial_port):
        tf = tiny_frame.tf_init(serial_port.write)
        tiny_frame.tf_register_callback(tiny_frame.TfMsgType.TYPE_ECHO, tiny_frame_receive_cb)

        TestUsbCom.DATA_SIZE_MAX -= tiny_frame.TF_FRAME_OVERHEAD_SIZE
        counter = TestUsbCom.LOOP_COUNT
        tx_history = bytearray()
        rx_history = bytearray()
        while True:
            if counter > 0:
                tx_data = generate_ascii_data(TestUsbCom.DATA_SIZE_MIN, TestUsbCom.DATA_SIZE_MAX)
                tf.send(tiny_frame.TfMsgType.TYPE_ECHO.value, tx_data, 0)
                tx_history += tx_data
                counter -= 1
                time.sleep(0.001)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)
                tf_rx_data = tiny_frame_receive_cb(None, None)
                rx_history += tf_rx_data

                if (counter == 0) and (len(rx_history) == len(tx_history)):
                    break

        assert rx_history == tx_history

        def test_usb_direct_loop(self, serial_port):
            counter = TestUsbCom.LOOP_COUNT
            while counter > 0:
                tx_data = generate_ascii_data(TestUsbCom.DATA_SIZE_MIN, TestUsbCom.DATA_SIZE_MAX)
                serial_port.write(tx_data)
                # Wait for the response
                while True:
                    if serial_port.in_waiting > 0:
                        # Read the incoming data
                        rx_data = serial_port.read(serial_port.in_waiting)
                        assert rx_data == tx_data
                        counter -= 1
                        break
        """
