#!/usr/bin/env python

""" Testing Memory class
"""

from interface_expander.Memory import Memory, MemoryType, MemoryAddressWidth


class TestMemory:
    def test_slave_address_packing(self):
        address_width = MemoryAddressWidth.TWO_BYTES
        mem = Memory(interface=None, slave_address=0x50, memory_type=MemoryType.RAM,
                     address_width=address_width, page_count=1, page_size=pow(2, 17))

        address = pow(2, address_width.value * 8) - 1
        mem._pack_slave_address(address) # Should not change the slave address
        assert mem.slave_address == 0x50

        # If the memory size is larger than 2^16, the additional address bits will 
        # be packed into the slave address byte.
        address = pow(2, address_width.value * 8)
        mem._pack_slave_address(address)
        assert mem.slave_address == 0b0101_0010  # 0x50 with additional address bit set

        address = pow(2, address_width.value * 8) - 1
        mem._pack_slave_address(address) # Should not change the slave address
        assert mem.slave_address == 0x50
