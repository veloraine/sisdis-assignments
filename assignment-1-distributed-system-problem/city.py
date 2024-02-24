import logging
import threading

from node_socket import UdpSocket


class City:

    def __init__(self, my_port: int, number_general: int) -> None:
        self.number_general = number_general
        self.my_port = my_port
        self.node_socket = UdpSocket(my_port)

    def start(self):
        """
        TODO
        :return: string
        """

        # Edge Cases
        # if honest general less than two
        if self.number_general < 2:
            logging.info("ERROR_LESS_THAN_TWO_GENERALS")
            return "ERROR_LESS_THAN_TWO_GENERALS"

        if self.number_general == 2:
            logging.info("ERROR_TWO_GENERALS")
            return "FAILED"
        
        # if honest general more than four
        if self.number_general > 4:
            logging.info("ERROR_MORE_THAN_FOUR_GENERALS")
            return "ERROR_MORE_THAN_FOUR_GENERALS"

        logging.info("Listen to incoming messages...")
        counter = 0
        orders = []
        while True:
            if counter == self.number_general:
                break
            msg = self.node_socket.listen()[0]
            logging.info(f"CITY MSG {msg}")
            msg_list = msg.split("~")
            sender = msg_list[0]
            order = int(msg_list[1].split("=")[1])

            orders.append(order)
            
            if order == 1:
                logging.info(f"{sender} ATTACK us!")
            else:
                logging.info(f"{sender} RETREAT from us!")
            
            counter += 1

        # conclusion
        logging.info("Concluding what happen...")
        # if 1 is more than 0, then ATTACK
        if orders.count(1) > orders.count(0):
            logging.info("GENERAL CONSENSUS: ATTACK")
            return "ATTACK"
        elif orders.count(1) < orders.count(0):
            logging.info("GENERAL CONSENSUS: RETREAT")
            return "RETREAT"
        
        logging.info("GENERAL CONSENSUS: FAILED")
        return "FAILED"


def thread_exception_handler(args):
    logging.error(f"Uncaught exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def main(city_port: int, number_general: int):
    threading.excepthook = thread_exception_handler
    try:
        logging.debug(f"city_port: {city_port}")
        logging.info(f"City is running...")
        logging.info(f"Number of loyal general: {number_general}")
        city = City(my_port=city_port, number_general=number_general)
        return city.start()

    except Exception:
        logging.exception("Caught Error")
        raise
