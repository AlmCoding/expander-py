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
import proto_i2c_msg as pm

REQUEST_LOOPS = 1
MIN_TX_SIZE = 1
MAX_DATA_SIZE = 64
TX_HISTORY = bytearray()
REQUEST_COUNTER = 0


def i2c_config(tf):
    msg = pm.encode_i2c_config_msg(pm.I2cId.I2C0, clock_rate=400000)
    tf.send(tiny_frame.TfMsgType.TYPE_I2C.value, msg, 0)


def i2c_send(tf):
    global REQUEST_COUNTER, TX_HISTORY

    write_data = "This is a test. ({}).".format(REQUEST_COUNTER)
    read_size = 8

    if pm.can_accept_master_request(pm.I2cId.I2C0, len(write_data), read_size) and REQUEST_COUNTER < REQUEST_LOOPS:
        print("Data: '{}'".format(write_data))
        tx_data = bytes(write_data, 'ascii')

        request = pm.MasterRequest(pm.I2cId.I2C0, slave_addr=0x01, write_data=tx_data, read_size=read_size)
        msg = pm.encode_i2c_master_request_msg(request=request)

        # print("Send msg (id={}, len={}, tx={}, seq={}) : {}"
        #      .format(REQUEST_COUNTER, len(msg), len(tx_data), pm.SEQ_NUM, msg))

        tf.send(tiny_frame.TfMsgType.TYPE_I2C.value, msg, 0)

        REQUEST_COUNTER += 1
        TX_HISTORY += tx_data


def main(arguments):
    global TX_HISTORY
    print("Uart test sender")

    with serial.Serial('COM4', 115200, timeout=1) as ser:
        tf = tiny_frame.tf_init(ser.write)

        # Configure i2c
        # i2c_config(tf)
        time.sleep(1)

        while True:
            i2c_send(tf)

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
                    if len(TX_HISTORY) == 0 and REQUEST_COUNTER >= REQUEST_LOOPS:
                        break
                else:
                    print("Data missmatch detected!")
                    print(TX_HISTORY[:rx_len])
                    print(pm.RX_BUFFER)
                    raise Exception("Data missmatch!")


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
