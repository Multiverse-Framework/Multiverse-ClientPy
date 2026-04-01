import unittest
import subprocess
import os
import time
import logging
import sys
from typing import List, Dict, Any
import numpy

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

from multiverse_client_py import MultiverseClient, MultiverseMetaData


class MultiverseConnector(MultiverseClient):
    def __init__(
        self,
        port: str,
        multiverse_meta_data: MultiverseMetaData,
        transport: str = "Tcp",
    ) -> None:
        if transport == "Tcp":
            self._transport = "Tcp"
            self._host = "127.0.0.1"
            self._server_port = "7000"
        elif transport == "Udp":
            self._transport = "Udp"
            self._host = "127.0.0.1"
            self._server_port = "8000"
        elif transport == "Zmq":
            self._transport = "Zmq"
            self._host = "tcp://127.0.0.1"
            self._server_port = "9000"
        else:
            raise ValueError("Unknown transport {}".format(transport))
        super().__init__(port, multiverse_meta_data)

    def loginfo(self, message: str) -> None:
        logger.info(f"{self._client_port}: {message}")

    def logwarn(self, message: str) -> None:
        logger.warning(f"{self._client_port}: {message}")

    def _run(self) -> None:
        self.loginfo("Start running the client.")
        self._connect_and_start()

    def send_and_receive_meta_data(self) -> None:
        self.loginfo("Sending request meta data: " + str(self.request_meta_data))
        self._communicate(True)
        self.loginfo("Received response meta data: " + str(self.response_meta_data))

    def send_and_receive_data(self) -> None:
        self.loginfo("Sending data: " + str(self.send_data))
        self._communicate(False)
        self.loginfo("Received data: " + str(self.receive_data))


multiverse_server_cpp_path = os.path.join(
    os.path.dirname(__file__), f"multiverse_server_cpp{'.exe' if os.name == 'nt' else ''}"
)
multiverse_server_rust_path = os.path.join(
    os.path.dirname(__file__), f"multiverse_server_rust{'.exe' if os.name == 'nt' else ''}"
)

multiverse_meta_data_dict = {
    "send": {
        "Tcp": [],
        "Udp": [],
        "Zmq": [],
    },
    "receive": {
        "Tcp": [],
        "Udp": [],
        "Zmq": [],
    },
}
object_names = [f"object_{i}" for i in range(10)]
attributes = {
    "position": [None] * 3,
    "quaternion": [None] * 4,
    "joint_angular_position": [None],
    "cmd_joint_angular_position": [None],
}
objects = {object_name: {} for object_name in object_names}


def get_ready_objects() -> Dict[str, List[str]]:
    ready_objects = {}
    for object_name, object_attributes in objects.items():
        for attribute_name, attribute_data in object_attributes.items():
            if not any([data is not None for data in attribute_data]):
                if object_name not in ready_objects:
                    ready_objects[object_name] = []
                ready_objects[object_name].append(attribute_name)
    return ready_objects


def get_random_request_meta_data(
    no_send: bool = False, no_receive: bool = False
) -> Dict[str, Any]:
    request_meta_data = {
        "send": {},
        "receive": {},
    }
    if not no_send:
        send_count = numpy.random.randint(1, len(object_names))
        for i in range(send_count):
            send_attribute_count = numpy.random.randint(1, len(attributes))
            send_attribute_names = numpy.random.choice(
                list(attributes.keys()), send_attribute_count, replace=False
            )
            request_meta_data["send"][object_names[i]] = send_attribute_names.tolist()
    if not no_receive:
        ready_objects = get_ready_objects()
        receive_count = numpy.random.randint(1, len(ready_objects) + 1)
        for i in range(receive_count):
            object_name = list(ready_objects.keys())[i]
            receive_attribute_count = numpy.random.randint(
                1, len(ready_objects[object_name]) + 1
            )
            receive_attribute_names = numpy.random.choice(
                ready_objects[object_name], receive_attribute_count, replace=False
            )
            request_meta_data["receive"][object_name] = receive_attribute_names.tolist()

    return request_meta_data


for n in range(10):
    for i, transport in enumerate(["Tcp", "Udp", "Zmq"]):
        multiverse_meta_data_dict["send"][transport].append(
            (
                MultiverseMetaData(
                    world_name="world",
                    simulation_name=f"send_{transport}_{n}",
                    length_unit="m",
                    angle_unit="rad",
                    mass_unit="kg",
                    time_unit="s",
                    handedness="rhs",
                ),
                f"{5000 + 6 * n + i}",
            )
        )
        multiverse_meta_data_dict["receive"][transport].append(
            (
                MultiverseMetaData(
                    world_name="world",
                    simulation_name=f"receive_{transport}_{n}",
                    length_unit="m",
                    angle_unit="rad",
                    mass_unit="kg",
                    time_unit="s",
                    handedness="rhs",
                ),
                f"{5000 + 6 * n + i + 1}",
            )
        )


def create_multiverse_clients(
    n_clients: int = 1, transport_type: str = "Tcp", client_role: str = "send"
) -> List[MultiverseConnector]:
    multiverse_connectors = []
    for client_id in range(n_clients):
        multiverse_meta_data, port = multiverse_meta_data_dict[client_role][
            transport_type
        ][client_id]
        multiverse_connector = MultiverseConnector(
            port=port,
            multiverse_meta_data=multiverse_meta_data,
            transport=transport_type,
        )
        multiverse_connector.run()
        multiverse_connectors.append(multiverse_connector)
    return multiverse_connectors


class MultiverseClientRustTestCase(unittest.TestCase):
    multiverse_server_path = multiverse_server_rust_path
    multiverse_server_process = None
    multiverse_connector = None

    @classmethod
    def setUpClass(cls):
        logger.info(f"Starting multiverse_server on {cls.multiverse_server_path}")
        cls.multiverse_server_process = subprocess.Popen(
            [
                cls.multiverse_server_path,
                "--transport",
                "tcp",
                "--bind",
                "127.0.0.1:7000",
                "--transport",
                "udp",
                "--bind",
                "127.0.0.1:8000",
                "--transport",
                "zmq",
                "--bind",
                "tcp://*:9000",
            ]
        )
        logger.info(f"multiverse_server started on {cls.multiverse_server_path}")

    @classmethod
    def tearDownClass(cls):
        logger.info(f"Stopping multiverse_server on {cls.multiverse_server_path}")
        cls.multiverse_server_process.kill()
        logger.info(f"multiverse_server stopped on {cls.multiverse_server_path}")
        time.sleep(1.0)  # Ensure the server has time to shut down

    def test_multiverse_server(self):
        start_time = time.time()
        self.assertTrue(self.multiverse_server_process.poll() is None)
        time.sleep(1.0)
        self.assertTrue(self.multiverse_server_process.poll() is None)
        self.assertLess(time.time() - start_time, 5.0)

    def check_multiverse_client_connect(self, transport_type: str, n_clients: int):
        if transport_type == "Udp":
            # Need time for the server to breathe before testing.
            time.sleep(1.0)
        start_time = time.time()
        send_multiverse_connectors = create_multiverse_clients(
            n_clients=n_clients, transport_type=transport_type, client_role="send"
        )
        receive_multiverse_connectors = create_multiverse_clients(
            n_clients=n_clients, transport_type=transport_type, client_role="receive"
        )
        time.sleep(0.1)
        for multiverse_connector in send_multiverse_connectors:
            multiverse_connector.stop()
        for multiverse_connector in receive_multiverse_connectors:
            multiverse_connector.stop()
        self.assertLess(time.time() - start_time, 10.0)

    def check_multiverse_client_send_request_meta_data(
        self, multiverse_connectors: List[MultiverseConnector]
    ):
        start_time = time.time()
        for multiverse_connector in multiverse_connectors:
            request_meta_data = get_random_request_meta_data(
                no_send=False, no_receive=True
            )
            for object_name in request_meta_data["send"]:
                if object_name not in objects:
                    objects[object_name] = {}
                for attribute_name in request_meta_data["send"][object_name]:
                    objects[object_name][attribute_name] = attributes[attribute_name]
            multiverse_connector.request_meta_data.update(request_meta_data)
            multiverse_connector.send_and_receive_meta_data()
        for multiverse_connector in multiverse_connectors:
            i = 0
            while "send" not in multiverse_connector.response_meta_data:
                multiverse_connector.loginfo("Waiting for send response meta data.")
                i += 1
                self.assertTrue(i < 100)
                time.sleep(0.01)
            send_objects = multiverse_connector.response_meta_data["send"]
            self.assertEqual(
                len(send_objects), len(multiverse_connector.request_meta_data["send"])
            )
            for object_name, send_attributes in send_objects.items():
                self.assertEqual(
                    len(send_attributes),
                    len(multiverse_connector.request_meta_data["send"][object_name]),
                )
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertLess(time.time() - start_time, 5.0)

    def check_multiverse_client_send_data(
        self, multiverse_connectors: List[MultiverseConnector], n_iterations: int = 1
    ):
        for _ in range(n_iterations):
            start_time = time.time()
            for multiverse_connector in multiverse_connectors:
                send_data = [start_time]
                send_objects = multiverse_connector.response_meta_data["send"]
                for send_attributes in send_objects.values():
                    for attribute_data in send_attributes.values():
                        data = numpy.random.normal(size=len(attribute_data))
                        send_data.extend(data.tolist())
                multiverse_connector.send_data = send_data
                multiverse_connector.send_and_receive_data()
            for multiverse_connector in multiverse_connectors:
                receive_data = multiverse_connector.receive_data
                self.assertEqual(receive_data[0], start_time)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()

    def check_multiverse_clients_send_data(self, transport_type: str, n_clients: int):
        multiverse_connectors = create_multiverse_clients(
            n_clients=n_clients, transport_type=transport_type, client_role="send"
        )
        self.check_multiverse_client_send_request_meta_data(multiverse_connectors)
        self.check_multiverse_client_send_data(multiverse_connectors)
        self.check_multiverse_client_send_data(multiverse_connectors, n_iterations=5)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()

    def check_multiverse_client_send_and_receive_request_meta_data(
        self,
        send_multiverse_connectors: List[MultiverseConnector],
        receive_multiverse_connectors: List[MultiverseConnector],
    ):
        start_time = time.time()
        for multiverse_connector in send_multiverse_connectors:
            request_meta_data = get_random_request_meta_data(
                no_send=False, no_receive=True
            )
            for object_name in request_meta_data["send"]:
                if object_name not in objects:
                    objects[object_name] = {}
                for attribute_name in request_meta_data["send"][object_name]:
                    objects[object_name][attribute_name] = attributes[attribute_name]
            multiverse_connector.request_meta_data.update(request_meta_data)
            multiverse_connector.send_and_receive_meta_data()
        for multiverse_connector in receive_multiverse_connectors:
            request_meta_data = get_random_request_meta_data(
                no_send=True, no_receive=False
            )
            for object_name in request_meta_data["receive"]:
                if object_name not in objects:
                    objects[object_name] = {}
                for attribute_name in request_meta_data["receive"][object_name]:
                    objects[object_name][attribute_name] = attributes[attribute_name]
            multiverse_connector.request_meta_data.update(request_meta_data)
            multiverse_connector.send_and_receive_meta_data()
        for multiverse_connector in send_multiverse_connectors:
            i = 0
            while "send" not in multiverse_connector.response_meta_data:
                multiverse_connector.loginfo("Waiting for send response meta data.")
                i += 1
                self.assertTrue(i < 100)
                time.sleep(0.01)
            send_objects = multiverse_connector.response_meta_data["send"]
            self.assertEqual(
                len(send_objects), len(multiverse_connector.request_meta_data["send"])
            )
            for object_name, send_attributes in send_objects.items():
                self.assertEqual(
                    len(send_attributes),
                    len(multiverse_connector.request_meta_data["send"][object_name]),
                )
        for multiverse_connector in receive_multiverse_connectors:
            i = 0
            while "receive" not in multiverse_connector.response_meta_data:
                multiverse_connector.loginfo("Waiting for receive response meta data.")
                i += 1
                self.assertTrue(i < 100)
                time.sleep(0.01)
            receive_objects = multiverse_connector.response_meta_data["receive"]
            self.assertEqual(
                len(receive_objects),
                len(multiverse_connector.request_meta_data["receive"]),
            )
            for object_name, receive_attributes in receive_objects.items():
                self.assertEqual(
                    len(receive_attributes),
                    len(multiverse_connector.request_meta_data["receive"][object_name]),
                )
        self.assertLess(time.time() - start_time, 5.0)

    def check_multiverse_client_send_and_receive_data(
        self,
        send_multiverse_connectors: List[MultiverseConnector],
        receive_multiverse_connectors: List[MultiverseConnector],
        n_iterations: int = 1,
    ):
        for i in range(n_iterations):
            logger.info(f"Iteration {i}")
            start_time = time.time()
            for send_multiverse_connector in send_multiverse_connectors:
                send_data = [start_time]
                send_objects = send_multiverse_connector.response_meta_data["send"]
                for object_name, send_attributes in send_objects.items():
                    for attribute_name, attribute_data in send_attributes.items():
                        data = numpy.random.normal(size=len(attribute_data))
                        send_data.extend(data.tolist())
                        objects[object_name][attribute_name] = data
                send_multiverse_connector.send_data = send_data
                send_multiverse_connector.send_and_receive_data()
            for send_multiverse_connector in send_multiverse_connectors:
                receive_data = send_multiverse_connector.receive_data
                self.assertEqual(receive_data[0], start_time)

            start_time = time.time()
            for receive_multiverse_connector in receive_multiverse_connectors:
                receive_multiverse_connector.send_data = [start_time]
                receive_multiverse_connector.send_and_receive_data()
            for receive_multiverse_connector in receive_multiverse_connectors:
                receive_data = receive_multiverse_connector.receive_data
                self.assertEqual(receive_data[0], start_time)
                index = 1
                receive_objects = receive_multiverse_connector.response_meta_data[
                    "receive"
                ]
                for object_name, receive_attributes in receive_objects.items():
                    for attribute_name, attribute_data in receive_attributes.items():
                        expected_data = objects[object_name][attribute_name]
                        received_attribute_data = receive_data[
                            index : index + len(attribute_data)
                        ]
                        numpy.testing.assert_array_almost_equal(
                            received_attribute_data, expected_data
                        )
                        index += len(attribute_data)

    def check_multiverse_clients_send_and_receive_data(
        self, transport_type: str, n_clients: int
    ):
        objects.clear()
        self.assertIn(transport_type, ["Tcp", "Udp", "Zmq"])
        self.assertGreaterEqual(n_clients, 1)
        self.assertLessEqual(n_clients, 3)
        send_multiverse_connectors = create_multiverse_clients(
            n_clients=n_clients, transport_type=transport_type, client_role="send"
        )
        receive_multiverse_connectors = create_multiverse_clients(
            n_clients=n_clients, transport_type=transport_type, client_role="receive"
        )
        self.check_multiverse_client_send_and_receive_request_meta_data(
            send_multiverse_connectors, receive_multiverse_connectors
        )
        self.check_multiverse_client_send_and_receive_data(
            send_multiverse_connectors, receive_multiverse_connectors
        )
        self.check_multiverse_client_send_and_receive_data(
            send_multiverse_connectors, receive_multiverse_connectors, n_iterations=5
        )
        for multiverse_connector in send_multiverse_connectors:
            multiverse_connector.stop()
        for multiverse_connector in receive_multiverse_connectors:
            multiverse_connector.stop()

    def test_multiverse_client_tcp_connect(self):
        self.check_multiverse_client_connect(transport_type="Tcp", n_clients=1)
        self.check_multiverse_client_connect(transport_type="Tcp", n_clients=2)
        self.check_multiverse_client_connect(transport_type="Tcp", n_clients=3)

    def test_multiverse_client_udp_connect(self):
        self.check_multiverse_client_connect(transport_type="Udp", n_clients=1)
        self.check_multiverse_client_connect(transport_type="Udp", n_clients=2)
        self.check_multiverse_client_connect(transport_type="Udp", n_clients=3)

    def test_multiverse_client_zmq_connect(self):
        self.check_multiverse_client_connect(transport_type="Zmq", n_clients=1)
        self.check_multiverse_client_connect(transport_type="Zmq", n_clients=2)
        self.check_multiverse_client_connect(transport_type="Zmq", n_clients=3)

    def test_multiverse_client_tcp_send_data_1_client(self):
        self.check_multiverse_clients_send_data(transport_type="Tcp", n_clients=1)

    def test_multiverse_client_tcp_send_data_2_clients(self):
        self.check_multiverse_clients_send_data(transport_type="Tcp", n_clients=2)

    def test_multiverse_client_tcp_send_data_3_clients(self):
        self.check_multiverse_clients_send_data(transport_type="Tcp", n_clients=3)

    def test_multiverse_client_udp_send_data_1_client(self):
        time.sleep(1.0)
        self.check_multiverse_clients_send_data(transport_type="Udp", n_clients=1)

    def test_multiverse_client_udp_send_data_2_clients(self):
        time.sleep(1.0)
        self.check_multiverse_clients_send_data(transport_type="Udp", n_clients=2)

    def test_multiverse_client_udp_send_data_3_clients(self):
        time.sleep(1.0)
        self.check_multiverse_clients_send_data(transport_type="Udp", n_clients=3)

    def test_multiverse_client_zmq_send_data_1_client(self):
        self.check_multiverse_clients_send_data(transport_type="Zmq", n_clients=1)

    def test_multiverse_client_zmq_send_data_2_clients(self):
        self.check_multiverse_clients_send_data(transport_type="Zmq", n_clients=2)

    def test_multiverse_client_zmq_send_data_3_clients(self):
        self.check_multiverse_clients_send_data(transport_type="Zmq", n_clients=3)

    def test_multiverse_client_tcp_send_and_receive_data_1_client(self):
        self.check_multiverse_clients_send_and_receive_data("Tcp", 1)

    def test_multiverse_client_tcp_send_and_receive_data_2_clients(self):
        self.check_multiverse_clients_send_and_receive_data("Tcp", 2)

    def test_multiverse_client_tcp_send_and_receive_data_3_clients(self):
        self.check_multiverse_clients_send_and_receive_data("Tcp", 3)

    def test_multiverse_client_udp_send_and_receive_data_1_client(self):
        time.sleep(1.0)
        self.check_multiverse_clients_send_and_receive_data("Udp", 1)

    def test_multiverse_client_udp_send_and_receive_data_2_clients(self):
        time.sleep(1.0)
        self.check_multiverse_clients_send_and_receive_data("Udp", 2)

    def test_multiverse_client_udp_send_and_receive_data_3_clients(self):
        time.sleep(1.0)
        self.check_multiverse_clients_send_and_receive_data("Udp", 3)

    def test_multiverse_client_zmq_send_and_receive_data_1_client(self):
        self.check_multiverse_clients_send_and_receive_data("Zmq", 1)

    def test_multiverse_client_zmq_send_and_receive_data_2_clients(self):
        self.check_multiverse_clients_send_and_receive_data("Zmq", 2)

    def test_multiverse_client_zmq_send_and_receive_data_3_clients(self):
        self.check_multiverse_clients_send_and_receive_data("Zmq", 3)


class MultiverseClientCppTestCase(MultiverseClientRustTestCase):
    multiverse_server_path = multiverse_server_cpp_path


if __name__ == "__main__":
    unittest.main()
