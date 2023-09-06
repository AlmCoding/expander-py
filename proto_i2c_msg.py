from proto.proto_py import i2c_pb2
from enum import Enum
import tiny_frame as tf


class I2cId(Enum):
    I2C0 = 0
    I2C1 = 1


I2C_INSTANCE = {
    I2cId.I2C0: None,
    I2cId.I2C1: None
}


class I2cMasterRequest:
    def __init__(self, slave_addr: int, write_data: bytes, read_size: int):
        self.pending = True
        self.request_id = None
        self.slave_addr = slave_addr
        self.write_data = write_data
        self.read_size = read_size
        self.sequence_id = None
        self.sequence_idx = None


class I2cInterface:
    def __init__(self, i2c_id: I2cId, i2c_addr: int, i2c_clock: int):
        self.i2c_id = i2c_id
        self.i2c_addr = i2c_addr
        self.i2c_clock = i2c_clock
        self.sequence_number = 0           # Proto message synchronization
        self.request_id_counter = 0
        self.sequence_id_counter = 0       # I2c request sequence counter
        self.master_queue_space = 8
        self.master_buffer_space = 128
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

        if isinstance(request, I2cMasterRequest):
            accept = self.master_queue_space > 0 and \
                     self.master_buffer_space >= len(request.write_data) + request.read_size

        return accept

    def get_pending_master_request_ids(self) -> list:
        return [request.request_id for rid, request in self.master_requests if request.pending]

    def get_completed_master_request_ids(self) -> list:
        return [request.request_id for rid, request in self.master_requests if not request.pending]

    def get_master_request(self, request_id: int, remove_completed=True):
        if request_id not in self.master_requests.keys():
            return None

        request = self.master_requests[request_id]
        if remove_completed and not request.pending:
            del self.master_requests[request_id]

        return request

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

        request.pending = True
        request.request_id = self.request_id_counter
        request.sequence_id = self.sequence_id_counter
        request.sequence_idx = 0
        self.master_requests[request.request_id] = request

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
                self.master_buffer_space = msg.master_status.buffer_space

            request_id = msg.master_status.request_id
            if request_id not in self.master_requests.keys():
                return

            self.master_requests[request_id].pending = False
            self.master_requests[request_id].read_data = msg.master_status.read_data


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
