from __future__ import annotations
from interface_expander.proto.proto_py import i2c_pb2
from enum import Enum
from typing import Callable
import interface_expander.tiny_frame as tf
import interface_expander.InterfaceExpander as intexp
import time

I2C_MASTER_QUEUE_SPACE = 4
I2C_MASTER_BUFFER_SPACE = 512
I2C_SLAVE_QUEUE_SPACE = 4
I2C_SLAVE_BUFFER_SPACE = pow(2, 16)
I2C_MAX_WRITE_SIZE = 128
I2C_MAX_READ_SIZE = 128


class I2cId(Enum):
    I2C0 = 0
    I2C1 = 1


I2C_INSTANCE: dict[I2cId, I2cInterface | None] = {I2cId.I2C0: None, I2cId.I2C1: None}


class ClockFreq(Enum):
    FREQ10K = 10e3
    FREQ40K = 40e3
    FREQ100K = 100e3
    FREQ400K = 400e3
    FREQ1M = 1e6


class AddressWidth(Enum):
    Bits7 = 0
    Bits8 = 1
    Bits10 = 2
    Bits16 = 3


class I2cConfigStatusCode(Enum):
    NOT_INIT = 0
    SUCCESS = 1
    BAD_REQUEST = 2
    INVALID_CLOCK_FREQ = 3
    INVALID_SLAVE_ADDR = 4
    INVALID_SLAVE_ADDR_WIDTH = 5
    INVALID_MEM_ADDR_WIDTH = 6
    INTERFACE_ERROR = 7
    PENDING = 8  # Not part of proto enum


class I2cStatusCode(Enum):
    NOT_INIT = 0
    SUCCESS = 1
    BAD_REQUEST = 2
    NO_SPACE = 3
    SLAVE_NO_ACK = 4
    SLAVE_EARLY_NACK = 5
    INTERFACE_ERROR = 6
    PENDING = 7  # Not part of proto enum


class I2cConfig:
    def __init__(
        self,
        clock_freq: ClockFreq,
        slave_addr: int,
        slave_addr_width: AddressWidth,
        mem_addr_width: AddressWidth = AddressWidth.Bits16,
    ):
        self.status_code = I2cConfigStatusCode.NOT_INIT
        self.request_id = None
        self.clock_freq = clock_freq
        self.slave_addr = slave_addr
        self.slave_addr_width = slave_addr_width
        self.mem_addr_width = mem_addr_width


class I2cMasterRequest:
    def __init__(self, slave_addr: int, write_data: bytes, read_size: int, callback_fn: Callable = None):
        self.status_code = I2cStatusCode.NOT_INIT
        self.request_id = None
        self.slave_addr = slave_addr
        self.write_data = write_data
        self.read_size = read_size
        self.sequence_id = None
        self.sequence_idx = None
        self.read_data = None
        self.callback_fn = callback_fn


class I2cSlaveRequest:
    def __init__(
        self, write_addr: int, write_data: bytes, read_addr: int, read_size: int, callback_fn: Callable = None
    ):
        self.status_code = I2cStatusCode.NOT_INIT
        self.request_id = None
        self.write_addr = write_addr
        self.write_data = write_data
        self.read_addr = read_addr
        self.read_size = read_size
        self.read_data = None
        self.callback_fn = callback_fn


class I2cSlaveNotification:
    def __init__(self, access_id: int, status_code: I2cStatusCode, write_data: bytes, read_data: bytes):
        self.access_id = access_id
        self.status_code = status_code
        self.write_data = write_data
        self.read_data = read_data


class I2cInterface:
    def __init__(self, i2c_id: I2cId, config: I2cConfig, callback_fn: Callable = None):
        self.expander = intexp.InterfaceExpander()
        self.i2c_id = i2c_id
        self.config = config
        self.callback_fn = callback_fn  # Slave notifications callback

        self.sequence_number = 0  # Proto message synchronization
        self.request_id_counter = 0

        self.master_queue_space = I2C_MASTER_QUEUE_SPACE
        self.master_buffer_space1 = I2C_MASTER_BUFFER_SPACE
        self.master_buffer_space2 = 0
        self.master_requests = {}

        self.slave_queue_space = I2C_SLAVE_QUEUE_SPACE
        self.slave_requests = {}
        self.slave_access_notifications = {}

        self.i2c_idm = i2c_pb2.I2cId.I2C0 if self.i2c_id == I2cId.I2C0 else i2c_pb2.I2cId.I2C1

        global I2C_INSTANCE
        I2C_INSTANCE[self.i2c_id] = self

        if self.apply_config(config) != I2cConfigStatusCode.SUCCESS:
            print("Failed to apply I2C configuration: %s" % config.status_code.name)
            raise RuntimeError("Failed to apply I2C configuration!")

    def __del__(self):
        global I2C_INSTANCE
        if I2C_INSTANCE and I2C_INSTANCE[self.i2c_id] is self:
            I2C_INSTANCE[self.i2c_id] = None

    def _check_request_sanity(self, request: I2cMasterRequest | I2cSlaveRequest) -> None:
        if isinstance(request, I2cMasterRequest):
            if request.slave_addr == self.config.slave_addr:
                raise ValueError("Slave address in request collides with own slave address!")
            if len(request.write_data) > I2C_MAX_WRITE_SIZE or request.read_size > I2C_MAX_READ_SIZE:
                raise ValueError("Write/read data size exceeds maximum allowed (%d)" % I2C_MAX_WRITE_SIZE)

        elif isinstance(request, I2cSlaveRequest):
            if len(request.write_data) == 0 and request.read_size == 0:
                raise ValueError("Write and read data cannot both be empty!")
            if len(request.write_data) > I2C_MAX_WRITE_SIZE or request.read_size > I2C_MAX_READ_SIZE:
                raise ValueError("Write/read data size exceeds maximum allowed (%d)" % I2C_MAX_WRITE_SIZE)
        else:
            raise ValueError("Invalid request type: {}".format(type(request)))

    def can_accept_request(self, request: I2cMasterRequest | I2cSlaveRequest) -> bool:
        self._check_request_sanity(request)
        accept = False

        if isinstance(request, I2cMasterRequest):
            if self.master_queue_space == 0:
                pass
            elif self.master_buffer_space1 >= (len(request.write_data) + request.read_size):
                accept = True
            elif (
                self.master_buffer_space1 >= len(request.write_data) and self.master_buffer_space2 >= request.read_size
            ):
                accept = True
            elif self.master_buffer_space1 >= request.read_size and self.master_buffer_space2 >= len(
                request.write_data
            ):
                accept = True
            elif self.master_buffer_space2 >= (len(request.write_data) + request.read_size):
                accept = True

        elif isinstance(request, I2cSlaveRequest):
            if self.slave_queue_space > 0:
                accept = True
        elif isinstance(request, I2cConfig):
            accept = True
        else:
            raise ValueError("Invalid request type: {}".format(type(request)))

        """
        if isinstance(request, I2cMasterRequest):
            if accept:
                print("Accept master request (sp1: %d, sp2: %d, qspace: %d)" %
                      (self.master_buffer_space1, self.master_buffer_space2, self.master_queue_space))
            else:
                print("Cannot accept master request (sp1: %d, sp2: %d, qspace: %d)" %
                      (self.master_buffer_space1, self.master_buffer_space2, self.master_queue_space))
        elif isinstance(request, I2cSlaveRequest):
            if accept:
                print("Accept slave request (qspace: %d)" % self.slave_queue_space)
            else:
                print("Cannot accept slave request (qspace: %d)" % self.slave_queue_space)
        """

        return accept

    def _update_free_space(self, request) -> None:
        if isinstance(request, I2cMasterRequest):
            self.master_queue_space -= 1
            assert self.master_queue_space >= 0

            bigger_section = max(len(request.write_data), request.read_size)
            smaller_section = min(len(request.write_data), request.read_size)

            if self.master_buffer_space1 >= (bigger_section + smaller_section):
                self.master_buffer_space1 -= bigger_section + smaller_section

            elif self.master_buffer_space1 >= bigger_section and self.master_buffer_space2 >= smaller_section:
                self.master_buffer_space1 = self.master_buffer_space2 - smaller_section
                self.master_buffer_space2 = 0

            elif self.master_buffer_space2 >= bigger_section and self.master_buffer_space1 >= smaller_section:
                self.master_buffer_space1 = self.master_buffer_space2 - bigger_section
                self.master_buffer_space2 = 0

            elif self.master_buffer_space2 >= (bigger_section + smaller_section):
                self.master_buffer_space2 -= bigger_section + smaller_section

            # print("Update space after send master request (id: %d, sp1: %d, sp2: %d)" %
            #      (request.request_id, self.master_buffer_space1, self.master_buffer_space2))

        elif isinstance(request, I2cSlaveRequest):
            self.slave_queue_space -= 1
            assert self.slave_queue_space >= 0

    def get_pending_master_request_ids(self) -> list[int]:
        return [
            request.request_id
            for rid, request in self.master_requests.items()
            if request.status_code == I2cStatusCode.PENDING
        ]

    def get_complete_master_request_ids(self) -> list[int]:
        return [
            request.request_id
            for rid, request in self.master_requests.items()
            if request.status_code != I2cStatusCode.PENDING
        ]

    def get_master_request(self, request_id: int) -> I2cMasterRequest:
        return self.master_requests[request_id]

    def pop_master_request(self, request_id: int) -> I2cMasterRequest:
        return self.master_requests.pop(request_id)

    def pop_complete_master_requests(self) -> dict[int, I2cMasterRequest]:
        complete_requests = {
            request.request_id: request
            for rid, request in self.master_requests.items()
            if request.status_code != I2cStatusCode.PENDING
        }
        for rid in complete_requests.keys():
            del self.master_requests[rid]
        return complete_requests

    def get_pending_slave_request_ids(self) -> list[int]:
        return [
            request.request_id
            for rid, request in self.slave_requests.items()
            if request.status_code == I2cStatusCode.PENDING
        ]

    def get_complete_slave_request_ids(self) -> list[int]:
        return [
            request.request_id
            for rid, request in self.slave_requests.items()
            if request.status_code != I2cStatusCode.PENDING
        ]

    def pop_complete_slave_requests(self) -> dict[int, I2cSlaveRequest]:
        complete_requests = {
            request.request_id: request
            for rid, request in self.slave_requests.items()
            if request.status_code != I2cStatusCode.PENDING
        }
        for rid in complete_requests.keys():
            del self.slave_requests[rid]
        return complete_requests

    def get_slave_access_notifications(self) -> dict[int, I2cSlaveNotification]:
        return self.slave_access_notifications.copy()

    def pop_slave_access_notifications(self, count=-1) -> dict[int, I2cSlaveNotification]:
        if count > 0:
            keys = list(self.slave_access_notifications.keys())[:count]
            notifications = {key: self.slave_access_notifications.pop(key) for key in keys}
        else:
            notifications = self.slave_access_notifications.copy()
            self.slave_access_notifications.clear()
        return notifications

    def apply_config(self, config: I2cConfig, timeout: float = 0.1) -> I2cConfigStatusCode:
        if not isinstance(config, I2cConfig):
            raise ValueError("Invalid configuration!")
        if config.slave_addr_width != AddressWidth.Bits7 and config.slave_addr_width != AddressWidth.Bits10:
            raise ValueError("Invalid slave-address-width configuration!")
        if config.mem_addr_width != AddressWidth.Bits8 and config.mem_addr_width != AddressWidth.Bits16:
            raise ValueError("Invalid memory-address-width configuration!")

        self.sequence_number += 1
        self.request_id_counter += 1

        config.status_code = I2cConfigStatusCode.PENDING
        config.request_id = self.request_id_counter
        self.config = config

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number

        msg.config_request.request_id = self.request_id_counter
        msg.config_request.clock_freq = int(config.clock_freq.value)
        msg.config_request.slave_addr = config.slave_addr
        msg.config_request.slave_addr_width = (
            i2c_pb2.AddressWidth.Bits7 if config.slave_addr_width == AddressWidth.Bits7 else i2c_pb2.AddressWidth.Bits10
        )
        msg.config_request.mem_addr_width = (
            i2c_pb2.AddressWidth.Bits8 if config.mem_addr_width == AddressWidth.Bits8 else i2c_pb2.AddressWidth.Bits16
        )

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)

        # Wait for response with timeout
        self.wait_for_response(config.request_id, timeout)
        return config.status_code

    def send_request(self, request: I2cMasterRequest | I2cSlaveRequest, timeout: float = 0.1) -> int:
        start_time = time.monotonic()
        while not self.can_accept_request(request):
            self.expander._read_all()
            if time.monotonic() - start_time > timeout:
                raise TimeoutError("Timeout waiting for request acceptance!")
        else:
            self.expander._read_all()

        if isinstance(request, I2cMasterRequest):
            return self._send_master_request(request)
        elif isinstance(request, I2cSlaveRequest):
            return self._send_slave_request(request)
        else:
            raise ValueError("Invalid request type!")

    def _send_master_request(self, request: I2cMasterRequest) -> int:
        if not isinstance(request, I2cMasterRequest):
            raise ValueError("Invalid request type!")

        """
        if request.slave_addr == self.config.slave_addr:
            raise ValueError("Slave address in request collides with own slave address!")

        if len(request.write_data) == 0 and request.read_size == 0:
            raise ValueError("Write and read data cannot both be empty!")

        if len(request.write_data) > I2C_MAX_WRITE_SIZE or request.read_size > I2C_MAX_READ_SIZE:
            raise ValueError("Write/read data size exceeds maximum allowed (%d)" % I2C_MAX_WRITE_SIZE)
        """

        self.sequence_number += 1
        self.request_id_counter += 1

        request.status_code = I2cStatusCode.PENDING
        request.request_id = self.request_id_counter

        self.master_requests[request.request_id] = request
        self._update_free_space(request)

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number

        msg.master_request.request_id = request.request_id
        msg.master_request.slave_addr = request.slave_addr
        msg.master_request.write_data = request.write_data
        msg.master_request.read_size = request.read_size
        msg.master_request.sequence_id = 0
        msg.master_request.sequence_idx = 0

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)
        return request.request_id

    def _send_slave_request(self, request: I2cSlaveRequest) -> int:
        if not isinstance(request, I2cSlaveRequest):
            raise Exception("Invalid request type!")

        """
        if len(request.write_data) == 0 and request.read_size == 0:
            raise ValueError("Write and read data cannot both be empty!")

        if len(request.write_data) > I2C_MAX_WRITE_SIZE or request.read_size > I2C_MAX_READ_SIZE:
            raise ValueError("Write/read data size exceeds maximum allowed (%d)" % I2C_MAX_WRITE_SIZE)
        """

        self.sequence_number += 1
        self.request_id_counter += 1

        request.status_code = I2cStatusCode.PENDING
        request.request_id = self.request_id_counter

        self.slave_requests[request.request_id] = request
        self._update_free_space(request)

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number

        msg.slave_request.request_id = request.request_id
        msg.slave_request.write_data = request.write_data
        msg.slave_request.read_size = request.read_size
        msg.slave_request.write_addr = request.write_addr
        msg.slave_request.read_addr = request.read_addr

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)
        return request.request_id

    def slave_scan(self, addr_range=range(1, 128), address_width=AddressWidth.Bits7) -> list[int]:
        found_devices = []
        for addr in addr_range:
            if addr == self.config.slave_addr:
                continue
            try:
                request = I2cMasterRequest(slave_addr=addr, write_data=bytes(), read_size=0)
                rid = self.send_request(request=request, timeout=0.1)
                req = self.wait_for_response(request_id=rid, timeout=0.1, pop_request=True)
                if req.status_code == I2cStatusCode.SUCCESS:
                    found_devices.append(addr)
                elif req.status_code != I2cStatusCode.SLAVE_NO_ACK:
                    raise RuntimeError("Unexpected status code (%s) from slave: 0x%02X" % (req.status_code.name, addr))
            except TimeoutError:
                pass
        return found_devices

    def wait_for_response(
        self, request_id: int, timeout: float, pop_request: bool = False
    ) -> I2cMasterRequest | I2cSlaveRequest | I2cConfig:
        if request_id in self.master_requests.keys():
            container = self.master_requests
            request = container[request_id]
            pending_code = I2cStatusCode.PENDING
        elif request_id in self.slave_requests.keys():
            container = self.slave_requests
            request = container[request_id]
            pending_code = I2cStatusCode.PENDING
        elif self.config.request_id == request_id:
            container = None
            request = self.config
            pending_code = I2cConfigStatusCode.PENDING
        else:
            raise ValueError("Unknown request id (id: %d)" % request_id)

        start_time = time.monotonic()
        while True:
            self.expander._read_all()
            if request.status_code != pending_code:
                break
            elif time.monotonic() - start_time > timeout:
                raise TimeoutError("Timeout waiting for response (id: %d)" % request_id)

        if pop_request and container and request_id in container.keys():
            del container[request_id]
        return request

    def wait_for_slave_notification(
        self, access_id: int | None, timeout: float, pop_notification: bool = False
    ) -> I2cSlaveNotification | None:
        notification = None
        length = 0
        if access_id is None or access_id < 0:
            length = len(self.slave_access_notifications)

        start_time = time.monotonic()
        while True:
            self.expander._read_all()
            if (access_id is None or access_id < 0) and len(self.slave_access_notifications) > length:
                _, notification = next(reversed(self.slave_access_notifications.items()))
                break
            elif access_id in self.slave_access_notifications.keys():
                notification = self.slave_access_notifications[access_id]
                break
            elif time.monotonic() - start_time > timeout:
                break

        if notification is not None and pop_notification:
            del self.slave_access_notifications[notification.access_id]
        return notification

    def _receive_msg_cb(self, msg: i2c_pb2.I2cMsg) -> None:
        inner_msg = msg.WhichOneof("msg")
        if inner_msg == "config_status":
            self._handle_config_status(msg)
        elif inner_msg == "master_status":
            self._handle_master_status(msg)
        elif inner_msg == "slave_status":
            self._handle_slave_status(msg)
        elif inner_msg == "slave_notification":
            self._handle_slave_notification(msg)
        else:
            raise ValueError("Invalid I2C message type!")

    def _handle_config_status(self, msg: i2c_pb2.I2cMsg):
        if msg.config_status.request_id == self.config.request_id:
            self.config.status_code = I2cConfigStatusCode(msg.config_status.status_code)
        else:
            raise ValueError("Received config status for unknown request (id: %d)" % msg.config_status.request_id)

    def _handle_master_status(self, msg: i2c_pb2.I2cMsg):
        if msg.sequence_number >= self.sequence_number:
            self.master_queue_space = msg.master_status.queue_space
            self.master_buffer_space1 = msg.master_status.buffer_space1
            self.master_buffer_space2 = msg.master_status.buffer_space2

        request_id = msg.master_status.request_id
        if request_id not in self.master_requests.keys():
            raise ValueError("Unknown master(%d) request (id: %d)" % (self.i2c_id.value, request_id))

        self.master_requests[request_id].status_code = I2cStatusCode(msg.master_status.status_code)
        self.master_requests[request_id].read_data = msg.master_status.read_data
        if self.master_requests[request_id].callback_fn:
            request = self.master_requests.pop(request_id)
            request.callback_fn(request)

    def _handle_slave_status(self, msg: i2c_pb2.I2cMsg):
        if msg.sequence_number >= self.sequence_number:
            self.slave_queue_space = msg.slave_status.queue_space

        request_id = msg.slave_status.request_id
        if request_id not in self.slave_requests.keys():
            raise ValueError("Unknown slave(%d) request status (id: %d) received!" % (self.i2c_id.value, request_id))

        self.slave_requests[request_id].status_code = I2cStatusCode(msg.slave_status.status_code)
        self.slave_requests[request_id].read_data = msg.slave_status.read_data
        if self.slave_requests[request_id].callback_fn:
            request = self.slave_requests.pop(request_id)
            request.callback_fn(request)

    def _handle_slave_notification(self, msg: i2c_pb2.I2cMsg):
        if msg.sequence_number >= self.sequence_number:
            self.slave_queue_space = msg.slave_notification.queue_space

        access_id = msg.slave_notification.access_id

        if access_id in self.slave_access_notifications.keys():
            raise ValueError("Duplicate slave(%d) access (id: %d)" % (self.i2c_id.value, access_id))

        status_code = I2cStatusCode(msg.slave_notification.status_code)
        notification = I2cSlaveNotification(
            msg.slave_notification.access_id,
            status_code,
            msg.slave_notification.write_data,
            msg.slave_notification.read_data,
        )
        self.slave_access_notifications[notification.access_id] = notification

        # print("Notification slave(%d) access (id: %d, w_data: %s (%d), r_data: %s (%d)"
        #      % (self.i2c_id.value, access_id, notification.write_data, len(notification.write_data),
        #         notification.read_data, len(notification.read_data)))

        if self.callback_fn:
            self.callback_fn(notification)


def _receive_i2c_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    """Receive a I2C message from the USB interface."""
    msg = i2c_pb2.I2cMsg()
    msg.ParseFromString(bytes(tf_msg.data))

    global I2C_INSTANCE
    if msg.i2c_id == i2c_pb2.I2cId.I2C0:
        instance = I2C_INSTANCE[I2cId.I2C0]
    else:
        instance = I2C_INSTANCE[I2cId.I2C1]

    if instance is not None:
        instance._receive_msg_cb(msg)
    else:
        raise RuntimeError("I2C instance (id: %s) is not initialized!" % msg.i2c_id.name)


tf.tf_register_callback(tf.TfMsgType.TYPE_I2C, _receive_i2c_msg_cb)
