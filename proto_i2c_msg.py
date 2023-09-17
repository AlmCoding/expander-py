from proto.proto_py import i2c_pb2
from enum import Enum
import tiny_frame as tf

I2C_MASTER_QUEUE_SPACE = 16
I2C_MASTER_BUFFER_SPACE = 8


class I2cId(Enum):
    I2C0 = 0
    I2C1 = 1


class I2cMasterStatusCode(Enum):
    NOT_INIT = 0
    NO_SPACE = 1
    PENDING = 2
    ONGOING = 3
    COMPLETE = 4
    SLAVE_BUSY = 5
    INTERFACE_ERROR = 6


I2C_INSTANCE = {
    I2cId.I2C0: None,
    I2cId.I2C1: None
}


class I2cMasterRequest:
    def __init__(self, slave_addr: int, write_data: bytes, read_size: int, callback_fn=None):
        self.status_code = I2cMasterStatusCode.NOT_INIT
        self.request_id = None
        self.slave_addr = slave_addr
        self.write_data = write_data
        self.read_size = read_size
        self.sequence_id = None
        self.sequence_idx = None
        self.callback_fn = callback_fn


class I2cInterface:
    def __init__(self, i2c_id: I2cId, i2c_addr: int, i2c_clock: int):
        self.i2c_id = i2c_id
        self.i2c_addr = i2c_addr
        self.i2c_clock = i2c_clock
        self.sequence_number = 0  # Proto message synchronization
        self.request_id_counter = 0
        self.sequence_id_counter = 0  # I2c request sequence counter
        self.master_queue_space = I2C_MASTER_QUEUE_SPACE
        self.master_buffer_space1 = I2C_MASTER_BUFFER_SPACE
        self.master_buffer_space2 = 0
        self.master_requests = {}

        if self.i2c_id == I2cId.I2C0:
            self.i2c_idm = i2c_pb2.I2cId.I2C0
        else:
            self.i2c_idm = i2c_pb2.I2cId.I2C1

        global I2C_INSTANCE
        I2C_INSTANCE[self.i2c_id] = self

    def __del__(self):
        global I2C_INSTANCE
        if I2C_INSTANCE[self.i2c_id] is self:
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

        return accept

    def update_free_space(self, request) -> None:
        if isinstance(request, I2cMasterRequest):
            self.master_queue_space -= 1

            if self.master_buffer_space1 >= (len(request.write_data) + request.read_size):
                self.master_buffer_space1 -= (len(request.write_data) + request.read_size)

            elif self.master_buffer_space1 >= len(request.write_data) and \
                    self.master_buffer_space2 >= request.read_size:
                self.master_buffer_space1 -= len(request.write_data)
                self.master_buffer_space2 -= request.read_size

            elif self.master_buffer_space1 >= request.read_size and \
                    self.master_buffer_space2 >= len(request.write_data):
                self.master_buffer_space1 -= request.read_size
                self.master_buffer_space2 -= len(request.write_data)

            elif self.master_buffer_space2 >= (len(request.write_data) + request.read_size):
                self.master_buffer_space2 -= (len(request.write_data) + request.read_size)

    def get_pending_master_request_ids(self) -> list[int]:
        return [request.request_id for rid, request in self.master_requests.items()
                if request.status_code == I2cMasterStatusCode.PENDING]

    def get_complete_master_request_ids(self) -> list[int]:
        return [request.request_id for rid, request in self.master_requests.items()
                if request.status_code != I2cMasterStatusCode.PENDING]

    def get_master_request(self, request_id: int) -> I2cMasterRequest:
        return self.master_requests[request_id]

    def pop_master_request(self, request_id: int) -> I2cMasterRequest:
        return self.master_requests.pop(request_id)

    def pop_complete_master_requests(self) -> dict[I2cMasterRequest]:
        complete_requests = {request.request_id: request for rid, request in self.master_requests.items()
                             if request.status_code != I2cMasterStatusCode.PENDING}
        for rid in complete_requests.keys():
            del self.master_requests[rid]
        return complete_requests

    def send_config_msg(self) -> None:
        self.sequence_number += 1

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number
        msg.cfg.clock_rate = self.i2c_clock

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)

    def send_master_request_msg(self, request) -> int:
        self.sequence_number += 1
        self.request_id_counter += 1
        self.sequence_id_counter += 1

        request.status_code = I2cMasterStatusCode.PENDING
        request.request_id = self.request_id_counter
        request.sequence_id = self.sequence_id_counter
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

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)
        return request.request_id

    def receive_msg_cb(self, msg: i2c_pb2.I2cMsg) -> None:
        inner_msg = msg.WhichOneof("msg")
        if inner_msg == "master_status":
            if msg.sequence_number >= self.sequence_number:
                self.master_queue_space = msg.master_status.queue_space
                self.master_buffer_space1 = msg.master_status.buffer_space1
                self.master_buffer_space2 = msg.master_status.buffer_space2

            request_id = msg.master_status.request_id
            if request_id not in self.master_requests.keys():
                return

            self.master_requests[request_id].status_code = I2cMasterStatusCode(msg.master_status.status_code)
            self.master_requests[request_id].read_data = msg.master_status.read_data
            if self.master_requests[request_id].callback_fn:
                request = self.master_requests.pop(request_id)
                request.callback_fn(request)


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
