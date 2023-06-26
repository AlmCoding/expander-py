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
import proto_msg as pm

TX_LOOPS = 100000
MIN_TX_SIZE = 1
MAX_DATA_SIZE = 64
TX_HISTORY = bytearray()
TX_COUNTER = 0


def uart_send(tf):
    global TX_COUNTER, TX_HISTORY
    if pm.TX_SPACE < MIN_TX_SIZE:
        return

    tx_data = "This is a test. With little data ({}).".format(TX_COUNTER)
    size = random.randint(MIN_TX_SIZE, min(MAX_DATA_SIZE, pm.TX_SPACE))
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))

    if pm.TX_SPACE >= len(tx_data) and TX_COUNTER < TX_LOOPS:
        print("Data: '{}'".format(tx_data))
        tx_data = bytes(tx_data, 'ascii')
        msg = pm.encode_uart_data_msg(pm.UartId.UART1, tx_data)
        print("Send msg (id={}, len={}, tx={}, seq={}) : {}".format(TX_COUNTER, len(msg), len(tx_data), pm.SEQ_NUM, msg))

        tf.send(tiny_frame.TfMsgType.TYPE_UART.value, msg, 0)
        pm.TX_SPACE -= len(tx_data)
        TX_COUNTER += 1
        TX_HISTORY += tx_data


def main(arguments):
    global TX_HISTORY
    print("TinyFrame test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)

        while True:
            uart_send(tf)
            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                # print(data)
                tf.accept(rx_data)

            rx_len = len(pm.RX_BUFFER)
            if rx_len > 0:
                if pm.RX_BUFFER[:rx_len] == TX_HISTORY[:rx_len]:
                    print("Loop ok for {} bytes: '{}'".format(rx_len, pm.RX_BUFFER.decode("ascii")))
                    TX_HISTORY = TX_HISTORY[rx_len:]
                    pm.RX_BUFFER.clear()
                    if len(TX_HISTORY) == 0 and TX_COUNTER >= TX_LOOPS:
                        break
                else:
                    print("Data missmatch detected!")
                    print(TX_HISTORY[:rx_len])
                    print(pm.RX_BUFFER)
                    raise Exception("Data missmatch!")


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
