#!/usr/bin/env python

""" Testing I2c slave write and read memory updates (no physical I2c communication involved)
"""

import random
import time

from msg import tiny_frame
from msg import proto_i2c_msg as pm
from helper import serial_port, generate_ascii_data


class TestI2cSlave:
    REQUEST_COUNT = 4 * 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 64 - tiny_frame.TF_FRAME_OVERHEAD_SIZE - 24

    I2C_CLOCK_FREQ = 400000
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02

    @staticmethod
    def generate_write_read_requests(count: int) -> list[pm.I2cSlaveRequest]:
        requests = []
        for _ in range(count):
            tx_data = generate_ascii_data(TestI2cSlave.DATA_SIZE_MIN, TestI2cSlave.DATA_SIZE_MAX)
            mem_addr = random.randint(0, pm.I2C_SLAVE_BUFFER_SPACE - len(tx_data) - 1)

            write_request = pm.I2cSlaveRequest(write_addr=mem_addr, write_data=tx_data, read_addr=0, read_size=0)
            read_request = pm.I2cSlaveRequest(write_addr=0, write_data=bytes(), read_addr=mem_addr,
                                              read_size=len(tx_data))
            requests.append(write_request)
            requests.append(read_request)
        return requests

    @staticmethod
    def i2c_send(i2c_int: pm.I2cInterface, request_queue: list[pm.I2cSlaveRequest]):
        if len(i2c_int.get_pending_slave_request_ids()) > 0:
            return

        if len(request_queue) and i2c_int.can_accept_request(request_queue[0]):
            request = request_queue.pop(0)
            rid = i2c_int.send_slave_request_msg(request=request)
            # print("Req: {}, w_data: {} ({}), r_size: {}".format(
            #    rid, request.write_data, len(request.write_data), request.read_size))
            assert len(i2c_int.get_pending_slave_request_ids()) > 0

    @staticmethod
    def verify_requests(i2c_int):
        assert len(i2c_int.get_pending_master_request_ids()) == 0
        assert len(i2c_int.get_complete_master_request_ids()) == 0

        complete_count = len(i2c_int.get_complete_slave_request_ids())
        if (complete_count % 2 != 0) or (complete_count == 0):
            return

        previous_write_request = None
        for request in i2c_int.pop_complete_slave_requests().values():
            assert request.status_code == pm.I2cStatusCode.SUCCESS
            if request.read_size == 0:  # Write request
                assert len(request.write_data) > 0
                previous_write_request = request
            else:  # Read request
                assert request.read_data == previous_write_request.write_data

    def test_i2c_slave_write_read(self, serial_port):
        tf = tiny_frame.tf_init(serial_port.write)
        cfg0 = pm.I2cConfig(clock_freq=TestI2cSlave.I2C_CLOCK_FREQ, slave_addr=TestI2cSlave.I2C0_SLAVE_ADDR,
                            slave_addr_width=pm.AddressWidth.Bits7, mem_addr_width=pm.AddressWidth.Bits16,
                            pullups_enabled=True)
        cfg1 = pm.I2cConfig(clock_freq=TestI2cSlave.I2C_CLOCK_FREQ, slave_addr=TestI2cSlave.I2C1_SLAVE_ADDR,
                            slave_addr_width=pm.AddressWidth.Bits7, mem_addr_width=pm.AddressWidth.Bits16,
                            pullups_enabled=True)
        i2c_int0 = pm.I2cInterface(i2c_id=pm.I2cId.I2C0, config=cfg0)
        i2c_int1 = pm.I2cInterface(i2c_id=pm.I2cId.I2C1, config=cfg1)
        time.sleep(1)

        requests_pipeline0 = TestI2cSlave.generate_write_read_requests(TestI2cSlave.REQUEST_COUNT // 4)
        requests_pipeline1 = TestI2cSlave.generate_write_read_requests(TestI2cSlave.REQUEST_COUNT // 4)

        while True:
            TestI2cSlave.i2c_send(i2c_int0, requests_pipeline0)
            TestI2cSlave.i2c_send(i2c_int1, requests_pipeline1)

            if serial_port.in_waiting > 0:
                # Read the incoming data
                rx_data = serial_port.read(serial_port.in_waiting)
                tf.accept(rx_data)

            TestI2cSlave.verify_requests(i2c_int0)
            TestI2cSlave.verify_requests(i2c_int1)

            if ((len(requests_pipeline0 + requests_pipeline1) == 0) and
                    (len(i2c_int0.get_pending_slave_request_ids() + i2c_int1.get_pending_slave_request_ids()) == 0)):
                break
