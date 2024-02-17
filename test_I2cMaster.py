#!/usr/bin/env python

""" Testing I2c master write/read
"""

import pytest
import serial
from msg import tiny_frame
from msg import proto_i2c_msg as pm
from helper import (get_com_port, generate_master_write_read_requests,
                    i2c_send_master_request, verify_master_write_read_requests)


@pytest.fixture()
def serial_port():
    with serial.Serial(get_com_port(), 115200, timeout=1) as ser:
        yield ser


class TestI2cMaster:
    REQUEST_COUNT = 4 * 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 64 - tiny_frame.TF_FRAME_OVERHEAD_SIZE - 24

    I2C_CLOCK_FREQ = 400000
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02
    FRAM_SLAVE_ADDR = 0x50

    FRAM_SIZE = 32768  # (== 2^15)
    FRAM_0_MIN_ADDR = 0
    FRAM_0_MAX_ADDR = FRAM_SIZE // 2 - 1
    FRAM_1_MIN_ADDR = FRAM_SIZE // 2
    FRAM_1_MAX_ADDR = FRAM_SIZE - 1

    def test_i2c_master_write_read_self(self, serial_port):
        # Test master using internal slave
        tf = tiny_frame.tf_init(serial_port.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=TestI2cMaster.I2C0_SLAVE_ADDR,
                                   i2c_clock=TestI2cMaster.I2C_CLOCK_FREQ, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=TestI2cMaster.I2C1_SLAVE_ADDR,
                                   i2c_clock=TestI2cMaster.I2C_CLOCK_FREQ, i2c_pullups=False)

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=TestI2cMaster.I2C1_SLAVE_ADDR,
                                                                 min_addr=0,
                                                                 max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=TestI2cMaster.DATA_SIZE_MAX,
                                                                 count=TestI2cMaster.REQUEST_COUNT // 4)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=TestI2cMaster.I2C0_SLAVE_ADDR,
                                                                 min_addr=0,
                                                                 max_addr=pm.I2C_SLAVE_BUFFER_SPACE - 1,
                                                                 max_size=TestI2cMaster.DATA_SIZE_MAX,
                                                                 count=TestI2cMaster.REQUEST_COUNT // 4)
        # requests_pipeline1 = []
        while True:
            i2c_send_master_request(i2c_int0, requests_pipeline0)
            i2c_send_master_request(i2c_int1, requests_pipeline1)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            verify_master_write_read_requests(i2c_int0)
            verify_master_write_read_requests(i2c_int1)

            if ((len(requests_pipeline0 + requests_pipeline1) == 0) and
                    (len(i2c_int0.get_pending_master_request_ids() + i2c_int1.get_pending_master_request_ids()) == 0)):
                break

    def test_i2c_master_write_read_fram(self, serial_port):
        # Test master using external FRAM
        tf = tiny_frame.tf_init(serial_port.write)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, i2c_addr=TestI2cMaster.I2C0_SLAVE_ADDR,
                                   i2c_clock=TestI2cMaster.I2C_CLOCK_FREQ, i2c_pullups=True)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, i2c_addr=TestI2cMaster.I2C1_SLAVE_ADDR,
                                   i2c_clock=TestI2cMaster.I2C_CLOCK_FREQ, i2c_pullups=False)

        requests_pipeline0 = generate_master_write_read_requests(slave_addr=TestI2cMaster.FRAM_SLAVE_ADDR,
                                                                 min_addr=TestI2cMaster.FRAM_0_MIN_ADDR,
                                                                 max_addr=TestI2cMaster.FRAM_0_MAX_ADDR,
                                                                 max_size=TestI2cMaster.DATA_SIZE_MAX,
                                                                 count=TestI2cMaster.REQUEST_COUNT // 4)
        requests_pipeline1 = generate_master_write_read_requests(slave_addr=TestI2cMaster.FRAM_SLAVE_ADDR,
                                                                 min_addr=TestI2cMaster.FRAM_1_MIN_ADDR,
                                                                 max_addr=TestI2cMaster.FRAM_1_MAX_ADDR,
                                                                 max_size=TestI2cMaster.DATA_SIZE_MAX,
                                                                 count=TestI2cMaster.REQUEST_COUNT // 4)
        requests_pipeline1 = []
        while True:
            i2c_send_master_request(i2c_int0, requests_pipeline0)
            # TestI2cMaster.i2c_send_master_request(i2c_int1, requests_pipeline1)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            verify_master_write_read_requests(i2c_int0)
            # TestI2cMaster.verify_master_write_read_requests(i2c_int1)

            if ((len(requests_pipeline0 + requests_pipeline1) == 0) and
                    (len(i2c_int0.get_pending_master_request_ids() + i2c_int1.get_pending_master_request_ids()) == 0)):
                break
