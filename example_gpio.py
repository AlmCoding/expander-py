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
OUTPUT_PATTERN = 1
REVERSED = False


def gpio_config():
    global REVERSED
    if REVERSED:
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


def gpio_generate():
    global SET_LOOPS, SET_COUNTER, REVERSED

    if SET_COUNTER < SET_LOOPS / 2:
        pattern = get_pattern()
        data = []

        for gpio_id, mode in pm.GpioInterface.Config.items():
            if mode == pm.GpioMode.OUTPUT_PUSHPULL or \
               mode == pm.GpioMode.OUTPUT_OPENDRAIN:
                data.append(pm.OutputData(gpio_id, pattern[0]))
                pattern = pattern[1:]

        pm.GpioInterface.send_data_msg(data)
        SET_COUNTER += 1
    else:
        if not REVERSED:
            REVERSED = True
            SET_COUNTER = 0
            gpio_config()
        else:
            exit(0)


def pattern_matches():
    if pm.GpioInterface.InputData[pm.GpioId.GPIO0] == pm.GpioInterface.InputData[pm.GpioId.GPIO4] and \
       pm.GpioInterface.InputData[pm.GpioId.GPIO1] == pm.GpioInterface.InputData[pm.GpioId.GPIO5] and \
       pm.GpioInterface.InputData[pm.GpioId.GPIO2] == pm.GpioInterface.InputData[pm.GpioId.GPIO6] and \
       pm.GpioInterface.InputData[pm.GpioId.GPIO3] == pm.GpioInterface.InputData[pm.GpioId.GPIO7]:
        return True
    else:
        return False


def main(arguments):
    global REVERSED
    print("Gpio test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)

        # Configure gpio
        REVERSED = False
        gpio_config()
        time.sleep(1)
        gpio_generate()

        while True:
            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)

            if pm.GpioInterface.Synchronized and pattern_matches():
                gpio_generate()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
