import logging
import multiprocessing
import pprint
import random
import sys
import time
from argparse import ArgumentParser
import node

# RUN IN PYTHON 3.8.8
import city

list_nodes = []

logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d:%H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

class NodeProcess(multiprocessing.Process):

    def run(self):
        try:
            super().run()
        except Exception:
            logger.error(f"{self.name} has an error")


def reload_logging_config_node(filename):
    from importlib import reload
    reload(logging)
    logging.basicConfig(format='%(asctime)-4s %(levelname)-6s %(threadName)s:%(lineno)-3d %(message)s',
                        datefmt='%H:%M:%S',
                        filename=f"logs/{filename}",
                        filemode='w',
                        level=logging.INFO)

def handle_exception(exc_type, exc_value, exc_traceback):
    logger.error(f"Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

def main():
    parser = ArgumentParser()
    parser.add_argument("-G", type=str, dest="generals",
                        help=" A string of generals (i.e. 'l,t,l,l'), where l is loyal and t is a traitor.  "
                             "The first general is the supreme general. "
                             "This argument is designed only to accept four generals",
                        default="l,t,l,l")
    parser.add_argument("-O", type=str, dest="order",
                        help=" The order the commander gives to the other generals (O ∈ {ATTACK,RETREAT})",
                        default="RETREAT")
    args = parser.parse_args()

    logger.info("Processing args...")
    roles = [True if x.strip() == "t" else False for x in args.generals.split(',')]
    order: str = args.order
    logger.debug(f"roles: {pprint.pformat(roles)}")
    logger.debug(f"order: {order}")
    logger.info("Done processing args...")
    execution(roles, order)


def execution(roles, order):
    logger = logging.getLogger(__name__)

    sys.excepthook = handle_exception

    logger.info("The main program is running...")
    logger.info("Determining the ports that will be used...")
    starting_port = random.randint(10000, 11000)
    port_used = [port for port in range(starting_port, starting_port + 4)]
    logger.debug(f"port_used: {port_used}")
    logger.info("Done determining the ports that will be used...")

    logger.info("Convert order string to binary...")
    order = node.Order.RETREAT if order.upper() == "RETREAT" else node.Order.ATTACK
    logger.debug(f"order: {order}")
    logger.info("Done converting string to binary...")

    logger.info("Start running multiple nodes...")
    for node_id in range(4):
        is_supreme_general = False if node_id else True
        file_name_prefix = f"general{node_id}" if not is_supreme_general else "supreme_general"
        reload_logging_config_node(f"{file_name_prefix}.txt")
        if is_supreme_general:
            process = NodeProcess(target=node.main, args=(
                roles[node_id],
                node_id,
                port_used,
                starting_port + node_id,
                order,
                is_supreme_general,
                starting_port + 4
            ))
        else:
            process = NodeProcess(target=node.main, args=(
                roles[node_id],
                node_id,
                port_used,
                starting_port + node_id,
                order,
                False,
                starting_port + 4
            ))
        process.start()
        list_nodes.append(process)
    logger.info("Done running multiple nodes...")
    logger.debug(f"number of running processes: {len(list_nodes)}")

    logger.info("Running city...")
    reload_logging_config_node(f"city.txt")
    number_general = roles.count(False)
    logger.debug(f"number_general: {number_general}")
    return city.main(starting_port+4, number_general)


if __name__ == '__main__':
    main()