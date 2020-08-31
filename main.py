from eagate_client import EAGateClient
from getpass import getpass
from requests import ConnectionError, Timeout
import argparse
import logging
import random
import time


def main(e, p):
    client = EAGateClient(e, p)
    while client.running:
        try:
            client.login()
            if not client.success:
                exit(1)
            logging.info(f'You currently have {client.get_stamp_count()} stamp(s).')
            last_time = -999999
            wait_for = 0
            while client.running:
                time.sleep(0.5)  # Sleep every 500ms to eliminate CPU usage when inactive
                curr_time = time.time()
                if curr_time - last_time <= wait_for:  # Refresh every interval
                    continue
                minutes_since_1500jst = (curr_time / 60 - 360) % 1440  # Pick card based on time since 15:00 JST
                best_card = int(
                    (0 + minutes_since_1500jst / 16.5) % 3)  # Some random formula based on personal obversation lol
                client.pick_card(best_card)
                last_time = curr_time
                wait_for = random.randint(600, 900)  # Random time between 10-15 minutes
        except (ConnectionError, Timeout):
            logging.error('Connection error. Retrying to connect in 30 seconds.')
            last_time = time.time()
            while client.running and time.time() - last_time <= 30:
                time.sleep(1)
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Automate the nono card game')
    parser.add_argument('--email', help='Your eagate email')
    parser.add_argument('--password', help='Your eagate password')
    parser.add_argument('--debug', action='store_const', const=True, default=False, help='Enable debug logging level')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s - %(levelname)s: %(message)s')
    email = args.email or input('Enter eagate email: ')
    password = args.password or getpass('Enter eagate password: ')
    main(email, password)
