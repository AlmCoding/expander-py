#!/usr/bin/env python

""" A simple python script template.
"""

import sys
import time
import string
import random
import serial
from msg import tiny_frame


INCLUDE_TINY_FRAME = True
TX_LOOPS = 1000
TX_COUNTER = 0
MIN_DATA_SIZE = 1
MAX_DATA_SIZE = 64
TX_HISTORY = bytearray()
BYTE_COUNTER = 0

if INCLUDE_TINY_FRAME:
    MAX_DATA_SIZE -= tiny_frame.TF_FRAME_OVERHEAD_SIZE
    if MIN_DATA_SIZE >= MAX_DATA_SIZE:
        MIN_DATA_SIZE = MAX_DATA_SIZE


def generate_data():
    global TX_COUNTER, MIN_DATA_SIZE, MAX_DATA_SIZE
    size = random.randint(MIN_DATA_SIZE, MAX_DATA_SIZE)
    tx_data = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))
    print("Send (%d): '%s' (%d bytes)" % (TX_COUNTER, tx_data, size))
    return tx_data.encode("utf-8")


def send_data(ser, tf):
    global TX_COUNTER, TX_HISTORY, MIN_DATA_SIZE, MAX_DATA_SIZE, BYTE_COUNTER, INCLUDE_TINY_FRAME
    # if len(TX_HISTORY) == 0 and TX_COUNTER < TX_LOOPS:
    if TX_COUNTER < TX_LOOPS:
        tx_data = generate_data()
        if INCLUDE_TINY_FRAME:
            tf.send(tiny_frame.TfMsgType.TYPE_ECHO.value, tx_data, 0)
        else:
            ser.write(tx_data)
        TX_HISTORY += tx_data
        BYTE_COUNTER += len(tx_data)
        TX_COUNTER += 1


def receive_data(rx_data):
    global TX_HISTORY, BYTE_COUNTER
    rx_len = len(rx_data)
    if rx_data == TX_HISTORY[:rx_len]:
        print("Loop ok for {} bytes: '{}'".format(rx_len, rx_data.decode("ascii")))
        TX_HISTORY = TX_HISTORY[rx_len:]
    else:
        print("Data missmatch detected!")
        print(TX_HISTORY[:rx_len])
        print(rx_data)
        raise Exception("Data missmatch!")


def receive_echo_msg_cb(_, tf_msg: tiny_frame.TF.TF_Msg) -> None:
    receive_data(bytes(tf_msg.data))


def main(arguments):
    global TX_HISTORY, BYTE_COUNTER
    print("Usb loop test")

    with serial.Serial('COM3', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)
        tiny_frame.tf_register_callback(tiny_frame.TfMsgType.TYPE_ECHO, receive_echo_msg_cb)
        start = time.time()

        while True:
            send_data(ser, tf)

            if ser.in_waiting > 0:
                # Read the incoming data
                rx_data = ser.read(ser.in_waiting)
                if INCLUDE_TINY_FRAME:
                    tf.accept(rx_data)
                else:
                    receive_data(rx_data)

            if len(TX_HISTORY) == 0 and TX_COUNTER >= TX_LOOPS:
                break

        duration = time.time() - start
        print("Send: %d bytes in %f seconds (%f kB/s)" % (BYTE_COUNTER, duration, BYTE_COUNTER / 1000 / duration))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
