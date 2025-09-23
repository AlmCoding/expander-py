#!/usr/bin/env python

"""Testing I2c master write/read"""

import pytest, random
from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import (
    I2cInterface,
    I2cConfig,
    ClockFreq,
    AddressWidth,
    I2cId,
    I2cMasterRequest,
    I2cStatusCode,
    I2C_SLAVE_BUFFER_SPACE,
    I2cSlaveRequest,
)
from tests.helper import generate_ascii_data, i2c_send_request


class TestI2cErrorNotifications:
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 128

    I2C_CLOCK_FREQ = ClockFreq.FREQ400K
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02
    FRAM_SLAVE_ADDR = 0x50

    def test_i2c_error_notify_invalid_slave_addr(self):
        # Test master using external FRAM
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(
            clock_freq=TestI2cErrorNotifications.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)

        random_size = random.randint(TestI2cErrorNotifications.DATA_SIZE_MIN, TestI2cErrorNotifications.DATA_SIZE_MAX)
        mem_addr = random.randint(0, I2C_SLAVE_BUFFER_SPACE - random_size)

        data_bytes = generate_ascii_data(random_size, random_size)
        addr_bytes = mem_addr.to_bytes(2, "big")
        tx_bytes = bytes(bytearray(addr_bytes) + bytearray(data_bytes))

        write_request = I2cMasterRequest(slave_addr=cfg0.slave_addr, write_data=tx_bytes, read_size=0)

        with pytest.raises(ValueError):
            rid = i2c0.send_request(request=write_request)
            # request = i2c0.wait_for_response(request_id=rid, timeout=0.1)
            # assert request.status_code == I2cStatusCode.BAD_REQUEST

        expander.disconnect()

    def test_i2c_error_notify_invalid_write_read_size(self):
        # Test master using external FRAM
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(
            clock_freq=TestI2cErrorNotifications.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)

        write_request = I2cMasterRequest(
            slave_addr=TestI2cErrorNotifications.FRAM_SLAVE_ADDR, write_data=bytes(), read_size=1024
        )
        with pytest.raises(ValueError):
            i2c0.send_request(request=write_request)

        data = generate_ascii_data(min_size=1024, max_size=1024)
        config_request = I2cSlaveRequest(write_addr=0, write_data=data, read_addr=0, read_size=0)
        with pytest.raises(ValueError):
            i2c0.send_request(request=config_request)

        expander.disconnect()
