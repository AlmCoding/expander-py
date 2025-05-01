from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2cMasterRequest


def complete_cb(request):
    print(f"Request complete cb (rid: {request.request_id}, status: {request.status_code}, "
          f"write_data: {request.write_data}, read_data: {request.read_data})")


def slave_access_cb(notification):
    print(f"Slave access notification (nid: {notification.access_id}, status: {notification.status_code}, "
          f"write_data: {notification.write_data}, read_data: {notification.read_data})")


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ400K,
                     slave_addr=0x01,
                     slave_addr_width=AddressWidth.Bits7,
                     mem_addr_width=AddressWidth.Bits16)
    i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)

    cfg1 = I2cConfig(clock_freq=ClockFreq.FREQ400K,
                     slave_addr=0x02,
                     slave_addr_width=AddressWidth.Bits7,
                     mem_addr_width=AddressWidth.Bits16)
    i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=slave_access_cb)

    request = I2cMasterRequest(slave_addr=0x02, write_data=bytes([0x00, 0x01, 0x42]), read_size=0,
                               callback_fn=complete_cb)
    rid = i2c0.send_request(request=request)

    notification = i2c1.wait_for_slave_notification(access_id=None, timeout=0.02, pop_notification=True)
    req = i2c0.wait_for_response(request_id=rid, timeout=0.02)

    expander.disconnect()
