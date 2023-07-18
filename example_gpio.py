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

SET_LOOPS = 16 * 1000
SET_COUNTER = 0
OUTPUT_PATTERN = 1
REVERSED = False


def gpio_config(tf):
    global REVERSED
    if REVERSED:
        msg = pm.encode_gpio_config_msg([
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
        msg = pm.encode_gpio_config_msg([
            pm.GpioConfig(pm.GpioId.GPIO0, pm.GpioMode.INPUT_PULLDOWN),
            pm.GpioConfig(pm.GpioId.GPIO1, pm.GpioMode.INPUT_PULLDOWN),
            pm.GpioConfig(pm.GpioId.GPIO2, pm.GpioMode.INPUT_PULLDOWN),
            pm.GpioConfig(pm.GpioId.GPIO3, pm.GpioMode.INPUT_PULLDOWN),
            pm.GpioConfig(pm.GpioId.GPIO4, pm.GpioMode.OUTPUT_PUSHPULL),
            pm.GpioConfig(pm.GpioId.GPIO5, pm.GpioMode.OUTPUT_PUSHPULL),
            pm.GpioConfig(pm.GpioId.GPIO6, pm.GpioMode.OUTPUT_PUSHPULL),
            pm.GpioConfig(pm.GpioId.GPIO7, pm.GpioMode.OUTPUT_PUSHPULL),
        ])

    tf.send(tiny_frame.TfMsgType.TYPE_GPIO.value, msg, 0)
    print("Send gpio config request")


def get_pattern():
    global SET_COUNTER
    # outputs = [bool(random.getrandbits(1)) for _ in range(2)]

    # Convert the number to its binary representation
    binary = bin(get_pattern.pattern_counter)[2:]
    # Pad the binary representation with leading zeros if necessary
    binary = binary.zfill(pm.GpioId.GPIO_CNT.value // 2)
    # Create a list of booleans representing the bits
    bool_list = [bit == '1' for bit in binary]

    get_pattern.pattern_counter += 1
    if get_pattern.pattern_counter > (pow(2, pm.GpioId.GPIO_CNT.value / 2) - 1):
        get_pattern.pattern_counter = 0

    print("Send pattern ({}): {}".format(SET_COUNTER, bool_list))
    return list(reversed(bool_list))


get_pattern.pattern_counter = 0


def pattern_matches():
    if pm.INPUT_DATA[pm.GpioId.GPIO0] == pm.INPUT_DATA[pm.GpioId.GPIO4] and \
       pm.INPUT_DATA[pm.GpioId.GPIO1] == pm.INPUT_DATA[pm.GpioId.GPIO5] and \
       pm.INPUT_DATA[pm.GpioId.GPIO2] == pm.INPUT_DATA[pm.GpioId.GPIO6] and \
       pm.INPUT_DATA[pm.GpioId.GPIO3] == pm.INPUT_DATA[pm.GpioId.GPIO7]:
        return True
    else:
        return False


def gpio_generate(tf):
    global SET_LOOPS, SET_COUNTER, REVERSED

    if SET_COUNTER < SET_LOOPS / 2:
        pattern = get_pattern()
        data = []

        for gpio_id, mode in pm.GpioConfigs.items():
            if mode == pm.GpioMode.OUTPUT_PUSHPULL or \
               mode == pm.GpioMode.OUTPUT_OPENDRAIN:
                data.append(pm.OutputData(gpio_id, pattern[0]))
                pattern = pattern[1:]

        msg = pm.encode_gpio_data_msg(data)
        tf.send(tiny_frame.TfMsgType.TYPE_GPIO.value, msg, 0)
        SET_COUNTER += 1
    else:
        if not REVERSED:
            REVERSED = True
            SET_COUNTER = 0
            gpio_config(tf)
        else:
            exit(0)


def main(arguments):
    global REVERSED
    print("Gpio test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)

        # Configure gpio
        REVERSED = False
        gpio_config(tf)
        time.sleep(1)
        gpio_generate(tf)

        while True:
            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)

            if pm.SYNCHRONIZED and pattern_matches():
                gpio_generate(tf)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
