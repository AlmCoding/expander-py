#!/usr/bin/env python

"""A simple python script template.
"""

import serial
import tf.TinyFrame as TF
import sys
import time

TYPE_DEFAULT = 0x00
TYPE_UART = 0x01
TYPE_PERIPHERAL = 0x02
TYPE_CENTRAL = 0x03


def fallback_listener(tf, msg):
    print("Fallback listener")
    print(msg.data)


def uart_listener(tf, msg):
    print("Uart listener")
    print(msg.data)


def main(arguments):
    print("TinyFrame test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = TF.TinyFrame()
        tf.SOF_BYTE = 0x01
        tf.ID_BYTES = 1
        tf.LEN_BYTES = 1
        tf.TYPE_BYTES = 1
        tf.CKSUM_TYPE = 'xor'
        tf.write = ser.write

        # Add listeners
        tf.add_fallback_listener(fallback_listener)
        tf.add_type_listener(TYPE_UART, uart_listener)

        # Send a frame
        tf.send(TYPE_UART, b"This are more than 64 bytes. This verifies that the frame is only processed when its complete.", 0)
        time.sleep(1)

        while True:
            if ser.in_waiting > 0:
                # Read the incoming data
                data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(data)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
