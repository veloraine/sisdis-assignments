import logging
import threading
from pprint import pformat

from node_socket import UdpSocket


class Order:
    RETREAT = 0
    ATTACK = 1


class General:

    def __init__(self, my_id: int, is_traitor: bool, my_port: int,
                 ports: list, node_socket: UdpSocket, city_port: int):
        self.ports = ports
        self.my_id = my_id
        self.city_port = city_port
        self.node_socket = node_socket
        self.my_port = my_port
        self.is_traitor = is_traitor

    def start(self):
        """
        TODO
        :return: None
        """
        # init list for orders
        orders = list()

        # send ready message to supreme general
        self.node_socket.send(f"ready", self.ports[0])
        msg_counter = 1

        # listen to incoming messages
        while True:
            if msg_counter == len(self.ports):
                break
            msg_list = self.listen_procedure()
            
            sender = msg_list[0]

            order = int((msg_list[1].split("="))[1])

            logging.info(f"Got incoming message from {sender}: {msg_list}")

            # append message to list
            orders.append(order)
            logging.info(f"Append message to a list: {orders}")

            self.sending_procedure(sender, order)
            msg_counter+=1

        # conclude action
        self.conclude_action(orders)

        return

    def listen_procedure(self):
        """
        TODO
        :return: list
        """
        # listen to incoming messages
        message, _ = self.node_socket.listen()
        logging.debug(f"Message received dari debug: {message}")
        msg_list = message.split("~")

        return msg_list

    def sending_procedure(self, sender, order):
        """
        TODO
        :param sender: sender id
        :param order: order
        :return: str or None
        """
        # if self is traitor, send reverse of the order      
        if self.is_traitor:
                        if order == 1:
                            order = 0
                        else:
                            order = 1

        # if sender is supreme general, send order to all generals
        if sender == "supreme_general":
            counter = 0
            for port in self.ports:
                # send to all but self and supreme general
                if port != self.my_port and port != self.ports[0]:
                    
                    logging.info(f"Done sending message to general {counter}...")
                    self.node_socket.send(f"general_{self.my_id}~order={order}", port)
                counter+=1
            return f"general_{self.my_id}~order={order}"
        return None

    def conclude_action(self, orders):
        """
        TODO
        :param orders: list
        :return: str or None
        """
        logging.info("Concluding action...")

        # if traitor return None
        if self.is_traitor:
            logging.info("I am a traitor")
            return None

        # if theres more 1 than 0, attack, else retreat
        if orders.count(1) > orders.count(0):
            logging.info("action: ATTACK")
            self.node_socket.send(f"general_{self.my_id}~action={Order.ATTACK}", self.city_port)
            return f"general_{self.my_id}~action={Order.ATTACK}"
            
        else:
            logging.info("action: RETREAT")
            self.node_socket.send(f"general_{self.my_id}~action={Order.RETREAT}", self.city_port)
            return f"general_{self.my_id}~action={Order.RETREAT}"


class SupremeGeneral(General):

    def __init__(self, my_id: int, is_traitor: bool, my_port: int, ports: list, node_socket: UdpSocket, city_port: int,
                 order: Order):
        super().__init__(my_id, is_traitor, my_port, ports, node_socket, city_port)
        self.order = order

    def sending_procedure(self, sender, order):
        """
        TODO
        :param sender: sender id
        :param order: order
        :return: list
        """

        # if traitor, send attack order to odd generals, retreat order to even generals
        counter = 0
        orders = []
        for port in self.ports:
            if port == self.my_port:
                counter+=1
                continue
            if self.is_traitor:
                if counter % 2 == 0:
                    self.node_socket.send(f"{sender}~order={Order.RETREAT}", port)
                    orders.append(Order.RETREAT)
                else:
                    self.node_socket.send(f"{sender}~order={Order.ATTACK}", port)
                    orders.append(Order.ATTACK)
            else:
                self.node_socket.send(f"{sender}~order={order}", port)
                orders.append(order)

        return orders

    def start(self):
        """
        TODO
        :return: None
        """
        logging.info("Supreme general is starting...")

        # check if all generals are ready
        logging.info("Wait until all generals are running...")

        counter = 1
        while True:
            if counter == len(self.ports):
                logging.debug("All generals are ready")
                break
            msg= self.node_socket.listen()
            if msg:
                logging.debug(msg)
                counter+=1
            
        # send to all generals
        logging.debug("Start sending orders to all generals...")
        result = self.sending_procedure("supreme_general", order=self.order)
        
        logging.info("Finish sending orders to all generals...")
        self.conclude_action([])

        return None

    def conclude_action(self, orders):
        """
        TODO
        :param orders: list
        :return: str or None
        """
        logging.info("Concluding action...")
        # if traitor return None
        if self.is_traitor:
            logging.info("I am a traitor")
            return None
        if self.order == Order.ATTACK:
            logging.info("ATTACK from the city...")
        else:
            logging.info("RETREAT from the city...")
            
        self.node_socket.send(f"supreme_general~action={self.order}", self.city_port)
        return f"supreme_general~action={self.order}"

def thread_exception_handler(args):
    logging.error(f"Uncaught exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def main(is_traitor: bool, node_id: int, ports: list,
         my_port: int = 0, order: Order = Order.RETREAT,
         is_supreme_general: bool = False, city_port: int = 0):
    threading.excepthook = thread_exception_handler
    try:
        if node_id > 0:
            logging.info(f"General {node_id} is running...")
        else:
            logging.info("Supreme general is running...")
        logging.debug(f"is_traitor: {is_traitor}")
        logging.debug(f"ports: {pformat(ports)}")
        logging.debug(f"my_port: {my_port}")
        logging.debug(f"order: {order}")
        logging.debug(f"is_supreme_general: {is_supreme_general}")
        logging.debug(f"city_port: {city_port}")

        if node_id == 0:
            obj = SupremeGeneral(my_id=node_id,
                                 city_port=city_port,
                                 is_traitor=is_traitor,
                                 node_socket=UdpSocket(my_port),
                                 my_port=my_port,
                                 ports=ports, order=order)
        else:
            obj = General(my_id=node_id,
                          city_port=city_port,
                          is_traitor=is_traitor,
                          node_socket=UdpSocket(my_port),
                          my_port=my_port,
                          ports=ports, )
        obj.start()
    except Exception:
        logging.exception("Caught Error")
        raise
