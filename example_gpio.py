#!/usr/bin/env python

"""A simple python script template.
"""

import sys
import enum
import time
import string
import random
import serial
import tiny_frame
import proto_gpio_msg as pm

SET_LOOPS = 16 * 100
SET_COUNTER = 0
OUTPUT_PATTERN = 0


def gpio_config(tf):
    msg = pm.encode_gpio_config_msg([
        pm.GpioConfig(pm.GpioId.GPIO1, pm.GpioMode.OUTPUT_PUSHPULL),
        pm.GpioConfig(pm.GpioId.GPIO2, pm.GpioMode.OUTPUT_PUSHPULL),
        pm.GpioConfig(pm.GpioId.GPIO3, pm.GpioMode.OUTPUT_PUSHPULL),
        pm.GpioConfig(pm.GpioId.GPIO4, pm.GpioMode.OUTPUT_PUSHPULL),
    ])
    tf.send(tiny_frame.TfMsgType.TYPE_GPIO.value, msg, 0)
    print("Send gpio config request")


def get_pattern():
    global OUTPUT_PATTERN
    # outputs = [bool(random.getrandbits(1)) for _ in range(2)]

    # Convert the number to its binary representation
    binary = bin(OUTPUT_PATTERN)[2:]
    # Pad the binary representation with leading zeros if necessary
    binary = binary.zfill(8)
    # Create a list of booleans representing the bits
    bool_list = [bit == '1' for bit in binary]

    OUTPUT_PATTERN += 1
    if OUTPUT_PATTERN > 15:
        OUTPUT_PATTERN = 0

    print("Send pattern:", bool_list)
    return list(reversed(bool_list))


def gpio_generate(tf):
    global SET_LOOPS, SET_COUNTER

    if SET_COUNTER < SET_LOOPS:
        pattern = get_pattern()
        msg = pm.encode_gpio_data_msg([
            pm.OutputData(pm.GpioId.GPIO1, pattern[0]),
            pm.OutputData(pm.GpioId.GPIO2, pattern[1]),
            pm.OutputData(pm.GpioId.GPIO3, pattern[2]),
            pm.OutputData(pm.GpioId.GPIO4, pattern[3]),
        ])
        tf.send(tiny_frame.TfMsgType.TYPE_GPIO.value, msg, 0)
        SET_COUNTER += 1
    else:
        exit(0)


def main(arguments):
    global TX_HISTORY
    print("Gpio test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)

        # Configure gpio
        gpio_config(tf)
        time.sleep(1)

        while True:
            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)

            if pm.SYNCHRONIZED:
                gpio_generate(tf)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
