from proto.proto_py import i2c_pb2
from enum import Enum
import msg.tiny_frame as tf


I2C_MASTER_QUEUE_SPACE = 4
I2C_MASTER_BUFFER_SPACE = 512
I2C_SLAVE_QUEUE_SPACE = 4
I2C_SLAVE_BUFFER_SPACE = 512


class I2cId(Enum):
    I2C0 = 0
    I2C1 = 1


class AddressWidth(Enum):
    Bits7 = 0
    Bits8 = 1
    Bits12 = 2
    Bits16 = 3


class I2cStatusCode(Enum):
    NOT_INIT = 0
    SUCCESS = 1
    BAD_REQUEST = 2
    NO_SPACE = 3
    SLAVE_NO_ACK = 4
    SLAVE_EARLY_NACK = 5
    INTERFACE_ERROR = 6
    PENDING = 7  # Not part of proto enum


I2C_INSTANCE = {
    I2cId.I2C0: None,
    I2cId.I2C1: None
}


class I2cConfig:
    def __init__(self, clock_freq: int, slave_addr: int, slave_addr_width: AddressWidth,
                 mem_addr_width: AddressWidth, pullups_enabled: bool):
        self.clock_freq = clock_freq
        self.slave_addr = slave_addr
        self.slave_addr_width = slave_addr_width
        self.mem_addr_width = mem_addr_width
        self.pullups_enabled = pullups_enabled


class I2cMasterRequest:
    def __init__(self, slave_addr: int, write_data: bytes, read_size: int, callback_fn=None):
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
    def __init__(self, write_addr: int, write_data: bytes, read_addr: int,  read_size: int, callback_fn=None):
        self.status_code = I2cStatusCode.NOT_INIT
        self.request_id = None
        self.write_addr = write_addr
        self.write_data = write_data
        self.read_addr = read_addr
        self.read_size = read_size
        self.read_data = None
        self.callback_fn = callback_fn


class I2cSlaveAccess:
    def __init__(self, access_id: int, status_code: I2cStatusCode, write_data: bytes, read_data: bytes):
        self.access_id = access_id
        self.status_code = status_code
        self.write_data = write_data
        self.read_data = read_data


class I2cInterface:
    def __init__(self, i2c_id: I2cId, config: I2cConfig):
        self.i2c_id = i2c_id
        self.config = config
        self.sequence_number = 0  # Proto message synchronization
        self.request_id_counter = 0
        self.sequence_id_counter = 0  # I2c request sequence counter
        self.master_queue_space = I2C_MASTER_QUEUE_SPACE
        self.master_buffer_space1 = I2C_MASTER_BUFFER_SPACE
        self.master_buffer_space2 = 0
        self.master_requests = {}
        self.slave_queue_space = I2C_SLAVE_QUEUE_SPACE
        self.slave_requests = {}
        self.slave_access_notifications = {}

        if self.i2c_id == I2cId.I2C0:
            self.i2c_idm = i2c_pb2.I2cId.I2C0
        else:
            self.i2c_idm = i2c_pb2.I2cId.I2C1

        global I2C_INSTANCE
        I2C_INSTANCE[self.i2c_id] = self

        self.send_config_msg(self.config)

    def __del__(self):
        global I2C_INSTANCE
        if I2C_INSTANCE and I2C_INSTANCE[self.i2c_id] is self:
            I2C_INSTANCE[self.i2c_id] = None

    def can_accept_request(self, request) -> bool:
        accept = False

        if isinstance(request, I2cMasterRequest) and self.master_queue_space > 0:
            if self.master_buffer_space1 >= (len(request.write_data) + request.read_size):
                accept = True
            elif self.master_buffer_space1 >= len(request.write_data) and \
                    self.master_buffer_space2 >= request.read_size:
                accept = True
            elif self.master_buffer_space1 >= request.read_size and \
                    self.master_buffer_space2 >= len(request.write_data):
                accept = True
            elif self.master_buffer_space2 >= (len(request.write_data) + request.read_size):
                accept = True

            # if accept:
            #    print("Accept master request ok (sp1: %d, sp2: %d)" %
            #          (self.master_buffer_space1, self.master_buffer_space2))

        elif isinstance(request, I2cSlaveRequest) and self.slave_queue_space > 0:
            accept = True

        return accept

    def update_free_space(self, request) -> None:
        if isinstance(request, I2cMasterRequest):
            self.master_queue_space -= 1

            bigger_section = max(len(request.write_data), request.read_size)
            smaller_section = min(len(request.write_data), request.read_size)

            if self.master_buffer_space1 >= (bigger_section + smaller_section):
                self.master_buffer_space1 -= (bigger_section + smaller_section)

            elif self.master_buffer_space1 >= bigger_section and self.master_buffer_space2 >= smaller_section:
                self.master_buffer_space1 = self.master_buffer_space2 - smaller_section
                self.master_buffer_space2 = 0

            elif self.master_buffer_space2 >= bigger_section and self.master_buffer_space1 >= smaller_section:
                self.master_buffer_space1 = self.master_buffer_space2 - bigger_section
                self.master_buffer_space2 = 0

            elif self.master_buffer_space2 >= (bigger_section + smaller_section):
                self.master_buffer_space2 -= (bigger_section + smaller_section)

            # print("Update space after send master request (id: %d, sp1: %d, sp2: %d)" %
            #      (request.request_id, self.master_buffer_space1, self.master_buffer_space2))

        elif isinstance(request, I2cSlaveRequest):
            self.slave_queue_space -= 1

    def get_pending_master_request_ids(self) -> list[int]:
        return [request.request_id for rid, request in self.master_requests.items()
                if request.status_code == I2cStatusCode.PENDING]

    def get_complete_master_request_ids(self) -> list[int]:
        return [request.request_id for rid, request in self.master_requests.items()
                if request.status_code != I2cStatusCode.PENDING]

    def get_master_request(self, request_id: int) -> I2cMasterRequest:
        return self.master_requests[request_id]

    def pop_master_request(self, request_id: int) -> I2cMasterRequest:
        return self.master_requests.pop(request_id)

    def pop_complete_master_requests(self) -> dict[I2cMasterRequest]:
        complete_requests = {request.request_id: request for rid, request in self.master_requests.items()
                             if request.status_code != I2cStatusCode.PENDING}
        for rid in complete_requests.keys():
            del self.master_requests[rid]
        return complete_requests

    def get_pending_slave_request_ids(self) -> list[int]:
        return [request.request_id for rid, request in self.slave_requests.items()
                if request.status_code == I2cStatusCode.PENDING]

    def get_complete_slave_request_ids(self) -> list[int]:
        return [request.request_id for rid, request in self.slave_requests.items()
                if request.status_code != I2cStatusCode.PENDING]

    def pop_complete_slave_requests(self) -> dict[I2cSlaveRequest]:
        complete_requests = {request.request_id: request for rid, request in self.slave_requests.items()
                             if request.status_code != I2cStatusCode.PENDING}
        for rid in complete_requests.keys():
            del self.slave_requests[rid]
        return complete_requests

    def get_slave_access_notifications(self) -> dict[I2cSlaveAccess]:
        return self.slave_access_notifications.copy()

    def pop_slave_access_notifications(self, count=-1) -> dict[I2cSlaveAccess]:
        notifications = {}
        if count > 0:
            keys = list(self.slave_access_notifications.keys())[:count]
            notifications = {key: self.slave_access_notifications.pop(key) for key in keys}
        else:
            notifications = self.slave_access_notifications.copy()
            self.slave_access_notifications.clear()
        return notifications

    def send_config_msg(self, config: I2cConfig) -> None:
        self.sequence_number += 1
        self.config = config

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number

        msg.config_request.request_id = 0
        msg.config_request.clock_freq = config.clock_freq
        msg.config_request.slave_addr = config.slave_addr
        msg.config_request.slave_addr_width = i2c_pb2.AddressWidth.Bits7
        msg.config_request.mem_addr_width = i2c_pb2.AddressWidth.Bits16
        msg.config_request.pullups_enabled = config.pullups_enabled

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)

    def send_master_sequence(self, sequence: list) -> list[int]:
        self.sequence_id_counter += 1
        seq_idx = len(sequence) - 1
        ids = []

        for request in sequence:
            request.sequence_id = self.sequence_id_counter
            request.sequence_idx = seq_idx
            ids.append(self.send_master_request_msg(request))
            seq_idx -= 1

        return ids

    def send_master_request_msg(self, request: I2cMasterRequest) -> int:
        self.sequence_number += 1
        self.request_id_counter += 1

        request.status_code = I2cStatusCode.PENDING
        request.request_id = self.request_id_counter

        if request.sequence_id is None:
            self.sequence_id_counter += 1
            request.sequence_id = self.sequence_id_counter
        if request.sequence_idx is None:
            request.sequence_idx = 0
        self.master_requests[request.request_id] = request
        self.update_free_space(request)

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number

        if isinstance(request, I2cMasterRequest):
            msg.master_request.request_id = request.request_id
            msg.master_request.slave_addr = request.slave_addr
            msg.master_request.write_data = request.write_data
            msg.master_request.read_size = request.read_size
            msg.master_request.sequence_id = request.sequence_id
            msg.master_request.sequence_idx = request.sequence_idx
        else:
            Exception("Invalid request!")

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)
        return request.request_id

    def send_slave_request_msg(self, request: I2cSlaveRequest) -> int:
        self.sequence_number += 1
        self.request_id_counter += 1

        request.status_code = I2cStatusCode.PENDING
        request.request_id = self.request_id_counter

        self.slave_requests[request.request_id] = request
        self.update_free_space(request)

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number

        if isinstance(request, I2cSlaveRequest):
            msg.slave_request.request_id = request.request_id
            msg.slave_request.write_data = request.write_data
            msg.slave_request.read_size = request.read_size
            msg.slave_request.write_addr = request.write_addr
            msg.slave_request.read_addr = request.read_addr
        else:
            Exception("Invalid request!")

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)
        return request.request_id

    def receive_msg_cb(self, msg: i2c_pb2.I2cMsg) -> None:
        inner_msg = msg.WhichOneof("msg")
        update_space = False
        if inner_msg == "config_status":
            pass

        elif inner_msg == "master_status":
            if msg.sequence_number >= self.sequence_number:
                self.master_queue_space = msg.master_status.queue_space
                self.master_buffer_space1 = msg.master_status.buffer_space1
                self.master_buffer_space2 = msg.master_status.buffer_space2
                update_space = True

            request_id = msg.master_status.request_id
            if request_id not in self.master_requests.keys():
                raise Exception("Unknown master(%d) request (id: %d)" % (self.i2c_id.value, request_id))
            if update_space:
                print("Response to master(%d) request (id: %d) | Update (sp1: %d, sp2: %d)" %
                      (self.i2c_id.value, request_id, self.master_buffer_space1, self.master_buffer_space2))
            else:
                print("Response to master(%d) request (id: %d)" % (self.i2c_id.value, request_id))

            self.master_requests[request_id].status_code = I2cStatusCode(msg.master_status.status_code)
            self.master_requests[request_id].read_data = msg.master_status.read_data
            if self.master_requests[request_id].callback_fn:
                request = self.master_requests.pop(request_id)
                request.callback_fn(request)

        elif inner_msg == "slave_status":
            if msg.sequence_number >= self.sequence_number:
                self.slave_queue_space = msg.slave_status.queue_space

            request_id = msg.slave_status.request_id

            if request_id not in self.slave_requests.keys():
                raise Exception("Unknown slave(%d) request (id: %d)" % (self.i2c_id.value, request_id))
            print("Response to slave(%d) request (id: %d)" % (self.i2c_id.value, request_id))

            self.slave_requests[request_id].status_code = I2cStatusCode(msg.slave_status.status_code)
            self.slave_requests[request_id].read_data = msg.slave_status.read_data
            if self.slave_requests[request_id].callback_fn:
                request = self.slave_requests.pop(request_id)
                request.callback_fn(request)

        elif inner_msg == "slave_notification":
            access_id = msg.slave_notification.access_id

            if access_id in self.slave_access_notifications.keys():
                raise Exception("Duplicate slave(%d) access (id: %d)" % (self.i2c_id.value, access_id))

            notification = I2cSlaveAccess(msg.slave_notification.access_id, msg.slave_notification.status_code,
                                          msg.slave_notification.write_data, msg.slave_notification.read_data)
            self.slave_access_notifications[notification.access_id] = notification

            print("Notification slave(%d) access (id: %d, w_data: %s (%d), r_data: %s (%d)"
                  % (self.i2c_id.value, access_id, notification.write_data, len(notification.write_data),
                     notification.read_data, len(notification.read_data)))
            
        else:
            raise Exception("Invalid I2C message type!")


def receive_i2c_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    global I2C_INSTANCE
    msg = i2c_pb2.I2cMsg()
    msg.ParseFromString(bytes(tf_msg.data))

    if msg.i2c_id == i2c_pb2.I2cId.I2C0:
        instance = I2C_INSTANCE[I2cId.I2C0]
    else:
        instance = I2C_INSTANCE[I2cId.I2C1]

    if instance:
        instance.receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_I2C, receive_i2c_msg_cb)
