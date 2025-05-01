#!/usr/bin/env python

""" Testing I2c slave write and read memory updates (no physical I2c communication involved)
"""

import random
from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import (I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2cSlaveRequest,
                                             I2C_SLAVE_BUFFER_SPACE, I2cStatusCode)
from tests.helper import generate_ascii_data


class TestI2cSlave:
    REQUEST_COUNT = 4 * 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 128

    I2C_CLOCK_FREQ = ClockFreq.FREQ400K
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02

    @staticmethod
    def generate_write_read_requests(count: int) -> list[I2cSlaveRequest]:
        requests = []
        for _ in range(count):
            tx_data = generate_ascii_data(TestI2cSlave.DATA_SIZE_MIN, TestI2cSlave.DATA_SIZE_MAX)
            mem_addr = random.randint(0, I2C_SLAVE_BUFFER_SPACE - len(tx_data) - 1)

            write_request = I2cSlaveRequest(write_addr=mem_addr, write_data=tx_data, read_addr=0, read_size=0)
            read_request = I2cSlaveRequest(write_addr=0, write_data=bytes(), read_addr=mem_addr,
                                           read_size=len(tx_data))
            requests.append(write_request)
            requests.append(read_request)
        return requests

    @staticmethod
    def i2c_send_slave_request(i2c_int: I2cInterface, request_queue: list[I2cSlaveRequest]):
        if len(request_queue) and i2c_int.can_accept_request(request_queue[0]):
            request = request_queue.pop(0)
            rid = i2c_int.send_request(request=request)
            print("Send slave({}) request (id: {}, w_addr: '{}', w_data: {} ({}), r_addr: '{}', r_size: {})"
                  .format(i2c_int.i2c_id.value, rid, request.write_addr, request.write_data,
                          len(request.write_data), request.read_addr, request.read_size))
            assert len(i2c_int.get_pending_slave_request_ids()) > 0
            return rid
        return None

    @staticmethod
    def verify_requests(i2c_int):
        assert len(i2c_int.get_pending_slave_request_ids()) == 0
      
        complete_count = len(i2c_int.get_complete_slave_request_ids())
        if (complete_count % 2 != 0) or (complete_count == 0):
            return

        previous_write_request = None
        for request in i2c_int.pop_complete_slave_requests().values():
            assert request.status_code == I2cStatusCode.SUCCESS
            if request.read_size == 0:  # Write request
                assert len(request.write_data) > 0
                previous_write_request = request
            else:  # Read request
                assert request.read_data == previous_write_request.write_data

    def test_i2c_slave_write_read(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(clock_freq=TestI2cSlave.I2C_CLOCK_FREQ,
                         slave_addr=0x01,
                         slave_addr_width=AddressWidth.Bits7,
                         mem_addr_width=AddressWidth.Bits16)
        cfg1 = I2cConfig(clock_freq=TestI2cSlave.I2C_CLOCK_FREQ,
                         slave_addr=0x02,
                         slave_addr_width=AddressWidth.Bits7,
                         mem_addr_width=AddressWidth.Bits16)

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)
        i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=None)

        requests_pipeline0 = TestI2cSlave.generate_write_read_requests(TestI2cSlave.REQUEST_COUNT // 4)
        requests_pipeline1 = TestI2cSlave.generate_write_read_requests(TestI2cSlave.REQUEST_COUNT // 4)

        while len(requests_pipeline0) > 0 or len(requests_pipeline1) > 0:
            _ = TestI2cSlave.i2c_send_slave_request(i2c0, requests_pipeline0)    # Write data
            ridr = TestI2cSlave.i2c_send_slave_request(i2c0, requests_pipeline0) # Read data
            i2c0.wait_for_response(request_id=ridr, timeout=0.1)
            TestI2cSlave.verify_requests(i2c0)

            _ = TestI2cSlave.i2c_send_slave_request(i2c1, requests_pipeline1)
            ridr = TestI2cSlave.i2c_send_slave_request(i2c1, requests_pipeline1)
            i2c1.wait_for_response(request_id=ridr, timeout=0.1)
            TestI2cSlave.verify_requests(i2c1)

        expander.disconnect()
