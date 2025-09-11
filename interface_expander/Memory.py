from interface_expander.I2cInterface import (
    I2cInterface,
    I2cMasterRequest,
    I2cStatusCode,
    I2C_MAX_READ_SIZE,
    I2C_MAX_WRITE_SIZE,
)
from intelhex import IntelHex
from enum import Enum
import math


class MemoryType(Enum):
    FRAM = 0  # No write status polling required
    EEPROM = 1  # Requires write status polling
    # FLASH = 2  # Requires erase before write


class MemoryAddressWidth(Enum):
    ONE_BYTE = 1
    TWO_BYTES = 2
    THREE_BYTES = 3
    FOUR_BYTES = 4


class Memory:
    def __init__(
        self,
        interface: I2cInterface,
        slave_address: int,
        memory_type: MemoryType,
        address_width: MemoryAddressWidth,
        page_count: int,
        page_size: int,
    ):
        self.interface = interface
        self.slave_address = slave_address
        self.memory_type = memory_type
        self.address_width = address_width
        self.page_count = page_count
        self.page_size = page_size

        self.memory_size = page_count * page_size
        # Some i2c memories use bits in the slave address to extend the address space
        self.additional_address_bits = 0
        if self.memory_size.bit_length() > self.address_width.value * 8:
            # Use address bit(s) in slave address byte
            self.additional_address_bits = (self.memory_size - 1).bit_length() - self.address_width.value * 8

        self.buffer = bytearray(self.memory_size)
        self.updated_sections = []

    def _pack_slave_address(self, address: int) -> int:
        # Pack the additional address bits into the slave address byte (used by some FRAMs/EEPROMs)
        if self.additional_address_bits == 0:
            return address

        additional_address = address >> (self.address_width.value * 8)
        if additional_address.bit_length() > self.additional_address_bits:
            raise ValueError(f"Address {address} exceeds the maximum allowed with additional address bits!")

        slave_mask = ~((1 << self.additional_address_bits) - 1)
        new_address = (self.slave_address & slave_mask) | additional_address
        self.slave_address = new_address

        max_value = (1 << (self.address_width.value * 8)) - 1
        masked_address = address & max_value
        return masked_address  # Does not exceed the address width (additional bits are packed into the slave address)

    def _unpack_slave_address(self, masked_address: int) -> int:
        # Unpack the additional address bits from the slave address byte
        if self.additional_address_bits == 0:
            return masked_address

        address_mask = (1 << self.additional_address_bits) - 1
        additional_address = (self.slave_address & address_mask) << (self.address_width.value * 8)
        address = masked_address | additional_address
        return address  # Restores the full address including additional bits

    def _wait_for_completion(self, request_ids: list[int], recursion: int = 0) -> None:
        max_repetitions = 10  # Maximum number of retries for read requests
        failed_requests = []

        for rid in request_ids:
            response = self.interface.wait_for_response(request_id=rid, timeout=0.1, pop_request=True)
            if response.status_code == I2cStatusCode.SLAVE_NO_ACK and recursion < max_repetitions:
                failed_requests.append(response)
            elif response.status_code == I2cStatusCode.SUCCESS:
                if response.read_data:
                    # Update the buffer with the read data
                    masked_address = int.from_bytes(response.write_data[: self.address_width.value], "big")
                    address = self._unpack_slave_address(masked_address)
                    self.buffer[address : address + len(response.read_data)] = response.read_data
            else:
                raise ValueError(f"Request {rid} failed with status: {response.status_code}")
        request_ids.clear()

        # Retry any requests that failed due to no ACK
        for request in failed_requests:
            rid = self.interface.send_request(request=request)
            request_ids.append(rid)

        if failed_requests:
            self._wait_for_completion(request_ids, recursion + 1)

    def read(self, address: int, length: int) -> bytes:
        if length == -1:
            length = self.memory_size - address
        if length < 0 or address < 0 or address + length > self.memory_size:
            raise ValueError("Invalid address or length for read operation!")

        request_count = math.ceil(length / I2C_MAX_READ_SIZE)
        pending_rids = []
        for i in range(request_count):
            offset = i * I2C_MAX_READ_SIZE
            current_address = address + offset
            read_length = min(I2C_MAX_READ_SIZE, length - offset)

            masked_addr = self._pack_slave_address(current_address)
            address_bytes = masked_addr.to_bytes(self.address_width.value, "big")

            request = I2cMasterRequest(slave_addr=self.slave_address, write_data=address_bytes, read_size=read_length)
            rid = self.interface.send_request(request=request)
            pending_rids.append(rid)

        self._wait_for_completion(pending_rids)
        return bytes(self.buffer[address : address + length])

    def write(self, address: int, data: bytes) -> None:
        if address < 0 or address + len(data) > self.memory_size:
            raise ValueError("Invalid address or data length for write operation!")

        self.buffer[address : address + len(data)] = data

        section_start = address
        section_end = address + len(data)
        for i, section in enumerate(self.updated_sections):
            start, end = section
            if start <= section_start and section_end <= end:  # Contained within existing section
                return
            elif section_start <= start and section_end >= end:  # Wraps entire section
                del self.updated_sections[i]
            elif start <= section_start <= end:  # Overlaps with start of existing section (or follows directly)
                del self.updated_sections[i]
                section_start = start
            elif start <= section_end <= end:  # Overlaps with end of existing section (or precedes directly)
                del self.updated_sections[i]
                section_end = end
            else:
                continue

        # Add the new section
        self.updated_sections.append((section_start, section_end))

    def flush(self) -> None:
        for section_start, section_end in self.updated_sections:
            if section_start < 0 or section_end > self.memory_size:
                raise ValueError("Invalid section range for flush operation!")
            self._flush_section(section_start, section_end)
        self.updated_sections.clear()

    def _flush_section(self, section_start: int, section_end: int) -> None:
        address = section_start
        length = section_end - section_start
        first_page = address // self.page_size
        last_page = (address + length - 1) // self.page_size
        page_count = last_page - first_page + 1
        max_write_length = I2C_MAX_WRITE_SIZE - self.address_width.value

        current_address = address
        page_start = first_page * self.page_size
        for _ in range(page_count):
            page_end = page_start + self.page_size

            while current_address < page_end and current_address < section_end:
                write_length = min(max_write_length, page_end - current_address, section_end - current_address)
                data = self.buffer[current_address : current_address + write_length]

                masked_addr = self._pack_slave_address(current_address)
                address_bytes = masked_addr.to_bytes(self.address_width.value, "big")

                self._send_write_request(address_bytes + data)
                current_address += write_length

            page_start += self.page_size

    def _send_write_request(self, write_data: bytes) -> None:
        max_retries = 42
        retry_counter = 0
        while retry_counter < max_retries:
            request = I2cMasterRequest(slave_addr=self.slave_address, write_data=write_data, read_size=0)
            rid = self.interface.send_request(request=request)
            response = self.interface.wait_for_response(request_id=rid, timeout=0.1, pop_request=True)

            if response.status_code == I2cStatusCode.SUCCESS:
                break
            elif response.status_code == I2cStatusCode.SLAVE_NO_ACK:
                retry_counter += 1
                continue  # If the memory is busy, we may need to wait and retry
            else:
                raise ValueError(f"Failed to flush memory: {response.status_code}")

        if retry_counter >= max_retries:
            raise TimeoutError(f"Failed to write to memory after {max_retries} retries!")

    def upload_bin_file(self, address: int, file_path: str) -> None:
        # Read data from file and write to memory
        with open(file_path, "rb") as file:
            data = file.read()
            self.write(address, data)
            self.flush()

    def download_bin_file(self, address: int, file_path: str, size: int = -1) -> None:
        # Read data from memory and save to file
        data = self.read(address, size)
        with open(file_path, "wb") as file:
            file.write(data)

    def upload_hex_file(self, file_path: str) -> None:
        # Read data from hex file and write to memory
        ih = IntelHex(file_path)
        for address, data in ih.todict().items():
            self.write(address, bytes([data]))
        self.flush()

    def download_hex_file(self, address: int, file_path: str, size: int = -1) -> None:
        # Read data from memory and save to hex file
        ih = IntelHex()
        data = self.read(address, size)
        ih.frombytes(data, offset=address)
        ih.tofile(file_path, format="hex")
