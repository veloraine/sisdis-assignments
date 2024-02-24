import unittest
from unittest import mock
from unittest.mock import patch

from city import City
from main import execution
from node import General, Order, SupremeGeneral
from node_socket import UdpSocket

class BgpTest(unittest.TestCase):

    def setUp(self) -> None:
        self.patch1 = mock.patch('logging.info')
        self.patch2 = mock.patch('logging.debug')
        mock_log_info = self.patch1.start()
        mock_log_debug = self.patch2.start()
        mock_log_info.return_value = None
        mock_log_debug.return_value = None

        self.patch3 = mock.patch('node_socket.UdpSocket.listen')
        self.patch4 = mock.patch('node_socket.UdpSocket.send')
        self.mock_incoming_message = self.patch3.start()
        self.mock_send_message = self.patch4.start()
        self.mock_send_message.return_value = None

        self.loyal_general = General(
            my_id=1,is_traitor=False,
            my_port=1,ports=[0,1,2,3],
            node_socket=UdpSocket(),
            city_port=0
        )

        self.loyal_supreme_general = SupremeGeneral(
            my_id=3, is_traitor=False,
            my_port=0, ports=[0, 1, 2, 3],
            node_socket=UdpSocket(),
            city_port=0,
            order=Order.ATTACK
        )

        self.city = City(
            my_port=0,
            number_general=4
        )

    def tearDown(self) -> None:
        self.patch1.stop()
        self.patch2.stop()
        self.patch3.stop()
        self.patch4.stop()

class BgpPublicTest(BgpTest):

    def test_listen_procedure_called_udpsocket_listen_once(self):
        self.mock_incoming_message.return_value = ("general_1~order=0", ("localhost", 123))
        self.loyal_general.listen_procedure()
        self.assertEqual(1,
                         self.mock_incoming_message.call_count)

    def test_listen_procedure_return_list(self):
        self.mock_incoming_message.return_value = ("general_1~order=0", ("localhost", 123))
        result = self.loyal_general.listen_procedure()
        self.assertEqual(result,
                         ['general_1', 'order=0'])

    def test_send_procedure_called_send_message_twice(self):
        self.loyal_general.sending_procedure("supreme_general", Order.ATTACK)
        self.assertEqual(2, self.mock_send_message.call_count)

    def test_send_procedure_not_supreme_general_return_none(self):
        result = self.loyal_general.sending_procedure("general_1", Order.ATTACK)
        self.assertEqual(None, result)

    def test_send_procedure_return_message(self):
        order = Order.ATTACK
        result = self.loyal_general.sending_procedure("supreme_general", order)
        expected = f"general_{self.loyal_general.my_id}~order={order}"
        self.assertEqual(expected, result)

    def test_concluding_action_called_send_message_once(self):
        self.loyal_general.conclude_action([Order.ATTACK, Order.RETREAT])
        self.assertEqual(1, self.mock_send_message.call_count)

    def test_concluding_action_return_message(self):
        result = self.loyal_general.conclude_action([Order.ATTACK, Order.RETREAT, Order.ATTACK])
        expected = f"general_{self.loyal_general.my_id}~action={Order.ATTACK}"
        self.assertEqual(result, expected)

    def test_start_method_called_all_procedure(self):
        temp = "node.General"
        patch_send_procedure = mock.patch(f"{temp}.sending_procedure")
        mock_send_procedure = patch_send_procedure.start()
        patch_listen_procedure = mock.patch(f"{temp}.listen_procedure")
        mock_listen_procedure = patch_listen_procedure.start()
        patch_conclude_action = mock.patch(f"{temp}.conclude_action")
        mock_conclude_action = patch_conclude_action.start()

        self.loyal_general.start()
        self.assertEqual(3, mock_send_procedure.call_count)
        self.assertEqual(3, mock_listen_procedure.call_count)
        self.assertEqual(1, mock_conclude_action.call_count)

        patch_conclude_action.stop()
        patch_send_procedure.stop()
        patch_listen_procedure.stop()

    def test_supreme_general_send_message_to_other_generals(self):
        self.loyal_supreme_general.sending_procedure(
            "supreme_general",
            self.loyal_supreme_general.order
        )
        self.assertEqual(3, self.mock_send_message.call_count)

    def test_supreme_general_send_message_return_list(self):
        result = self.loyal_supreme_general.sending_procedure(
            "supreme_general",
            self.loyal_supreme_general.order
        )
        expected = [self.loyal_supreme_general.order for i in range(3)]
        self.assertEqual(expected, result)

    def test_supreme_general_send_information_to_city_once(self):
        self.loyal_supreme_general.conclude_action([])
        self.mock_send_message.assert_called_once()

    def test_supreme_general_send_message_return_correct_format(self):
        result = self.loyal_supreme_general.conclude_action([])
        expected = f"supreme_general~action={self.loyal_supreme_general.order}"
        self.assertEqual(expected, result)

    def test_supreme_general_called_all_procedures(self):
        temp = "node.SupremeGeneral"
        patch_send_procedure = mock.patch(f"{temp}.sending_procedure")
        mock_send_procedure = patch_send_procedure.start()
        patch_conclude_action = mock.patch(f"{temp}.conclude_action")
        mock_conclude_action = patch_conclude_action.start()
        self.loyal_supreme_general.start()
        self.assertEqual(1, mock_send_procedure.call_count)
        self.assertEqual(1, mock_conclude_action.call_count)
        patch_conclude_action.stop()
        patch_send_procedure.stop()

    def test_city_listen_according_number_general(self):
        self.mock_incoming_message.side_effect = [
            ("general_1~order=0", ("localhost", 123)),
            ("supreme_general~order=0", ("localhost", 123)),
            ("general_2~order=0", ("localhost", 123)),
            ("general_3~order=0", ("localhost", 123)),
        ]
        self.city.start()
        self.assertEqual(self.city.number_general, self.mock_incoming_message.call_count)

    def test_city_no_consensus(self):
        self.mock_incoming_message.side_effect = [
            ("general_1~order=1", ("localhost", 123)),
            ("supreme_general~order=0", ("localhost", 123)),
            ("general_2~order=1", ("localhost", 123)),
            ("general_3~order=0", ("localhost", 123)),
        ]
        result = self.city.start()
        expected = "FAILED"
        self.assertEqual(expected, result)


class BgpPublicGrader(unittest.TestCase):

    def test_three_loyal_generals_one_traitor_retreat_return_retreat(self):
        result = execution([False, True, False, False], "RETREAT")
        expected = "RETREAT"
        self.assertEqual(expected, result)

    def test_three_loyal_generals_one_supreme_general_traitor_attack_return_attack(self):
        result = execution([True, False, False, False], "ATTACK")
        expected = "ATTACK"
        self.assertEqual(expected, result)

    def test_one_loyal_general_three_traitors_retreat_return_error(self):
        result = execution([True, True, True, False], "RETREAT")
        expected = "ERROR_LESS_THAN_TWO_GENERALS"
        self.assertEqual(expected, result)

    def test_two_loyal_generals_two_traitors_attack_return_fail(self):
        result = execution([False, True, True, False], "ATTACK")
        expected = "FAILED"
        self.assertEqual(expected, result)


if __name__ == '__main__':
    unittest.main()
