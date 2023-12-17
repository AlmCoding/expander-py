#!/usr/bin/env python

""" A simple python script template.
"""

import sys
import enum
import time
import string
import random
import serial
import tiny_frame
import proto_uart_msg as pm

TX_LOOPS = 1000
TX_COUNTER = 0
MIN_DATA_SIZE = 1
MAX_DATA_SIZE = 64
TX_HISTORY = bytearray()

MAX_DATA_SIZE -= tiny_frame.TF_FRAME_OVERHEAD_SIZE + 24
if MIN_DATA_SIZE >= MAX_DATA_SIZE:
    MIN_DATA_SIZE = MAX_DATA_SIZE


def uart_send(uart_int: pm.UartInterface):
    global TX_COUNTER, TX_HISTORY, MIN_DATA_SIZE, MAX_DATA_SIZE

    # tx_data = "This is a test. With little data ({}).".format(TX_COUNTER)
    size = random.randint(MIN_DATA_SIZE, min(MAX_DATA_SIZE, max(uart_int.tx_buffer_space, MIN_DATA_SIZE)))
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))

    if uart_int.can_accept_request(len(tx_data)) and TX_COUNTER < TX_LOOPS:
        print("Data ({}): '{}'".format(len(tx_data), tx_data))
        tx_data = bytes(tx_data, 'ascii')
        uart_int.send_data_msg(tx_data)

        TX_COUNTER += 1
        TX_HISTORY += tx_data


def main(arguments):
    global TX_HISTORY
    print("Uart test sender")

    with serial.Serial('COM3', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        uart_int = pm.UartInterface(uart_id=pm.UartId.UART0, baud_rate=115200)

        # Configure uart
        uart_int.send_config_msg()

        while True:
            uart_send(uart_int)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)

            rx_len = len(uart_int.rx_buffer)
            if rx_len > 0:
                if uart_int.rx_buffer == TX_HISTORY[:rx_len]:
                    print("Loop ok for {} bytes: '{}'".format(rx_len, uart_int.rx_buffer.decode("ascii")))
                    TX_HISTORY = TX_HISTORY[rx_len:]
                    uart_int.rx_buffer.clear()
                    if len(TX_HISTORY) == 0 and TX_COUNTER >= TX_LOOPS:
                        break
                else:
                    print("Data missmatch detected!")
                    print(TX_HISTORY[:rx_len])
                    print(uart_int.rx_buffer)
                    raise Exception("Data missmatch!")


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
