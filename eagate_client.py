from bs4 import BeautifulSoup
import concurrent.futures
import img_manip_wrapper as img_manip
import logging
import requests
import requests.utils
import signal


def process_image_url(url):
    img = img_manip.load_image(url)   # Load captcha
    img = img_manip.remove_background(img)
    vals = img_manip.get_stat_values(img)
    del img
    return vals


class EAGateClient:
    def __init__(self, email, pw):
        signal.signal(signal.SIGINT, self.onexit)
        signal.signal(signal.SIGTERM, self.onexit)
        self.running = True
        self.success = False
        self.sess = requests.Session()
        self.email = email
        self.password = pw

    def login(self):
        self.success = False
        if len(self.email) < 8 or len(self.password) < 8:
            logging.error('Email and/or password are shorter than 8 characters. Exiting...')
            return
        logging.info('Logging in to eagate...')
        self.sess.get('https://p.eagate.573.jp/gate/p/login.html')  # Visit login page to start session
        while not self.success:
            r = self.sess.post('https://p.eagate.573.jp/gate/p/common/login/api/kcaptcha_generate.html')  # Init captcha
            data = r.json()['data']
            image_urls = list(map(lambda xx: xx['img_url'], data['choicelist'][:-1])) + [data['correct_pic']]
            image_keys = list(map(lambda xy: xy['key'], data['choicelist'][:-1]))
            kcsess = data['kcsess']
            with concurrent.futures.ThreadPoolExecutor() as executor:  # Download images concurrently, not sequentially
                futures = [executor.submit(process_image_url, url) for url in image_urls]
                color_vals = [f.result() for f in futures]
            tg = color_vals[-1]
            error_vals = list(map(lambda i_x: (i_x[0],
                                               (i_x[1][0] - tg[0]) ** 2 + (i_x[1][1] - tg[1]) ** 2 +
                                               (i_x[1][2] - tg[2]) ** 2 + (i_x[1][3] - tg[3]) ** 2 +
                                               (i_x[1][4] - tg[4]) ** 2 + (i_x[1][5] - tg[5]) ** 2),
                                  enumerate(color_vals[:-1])))  # Euclidian distance for simplicity's sake
            error_vals = sorted(error_vals, key=lambda xz: xz[1])  # Best images go on top
            for x in range(len(error_vals)):
                logging.debug(f'{image_urls[error_vals[x][0]]}: {color_vals[error_vals[x][0]]} | {error_vals[x][1]}')
            logging.debug(f'{image_urls[-1]}: {color_vals[-1]}')
            captcha = f'k_{kcsess}_'  # Generate captcha input code
            for x in range(len(error_vals)):
                if x > 0:
                    captcha += '_'
                if x == error_vals[0][0] or x == error_vals[1][0]:
                    captcha += image_keys[x]
            r = self.sess.post('https://p.eagate.573.jp/gate/p/common/login/api/login_auth.html', data={  # Login
                'login_id': self.email,
                'pass_word': self.password,
                'otp': '',
                'resrv_url': '',
                'captcha': captcha
            })
            data = r.json()
            if 'fail_code' in data and data['fail_code'] != 0:
                if data['fail_code'] == 200:  # Incorrect login
                    logging.error('Incorrect credentials. Exiting...')
                    return
                if data['fail_code'] == 100:  # Failed captcha
                    logging.warning('Incorrect captcha. Retrying...')
                else:  # Some other error
                    logging.error(f'Unknown error code {data["fail_code"]}. Exiting...')
                    return
            else:
                logging.info('Successful login.')
                self.success = True

    def pick_card(self, ind=0):
        if not self.success:  # Check if logged in successfully
            return
        ind = min(2, max(0, ind))
        data = self.visit_card_page()
        if 'img/01/chara_done.png' in data:  # If no card game available
            logging.debug('Waiting until card game is available...')
        elif '<strong>e-amusement' in data:  # If session expired
            logging.info('Session expired. Re-logging...')
            self.login()  # Re-login and redo card pick
            self.pick_card(ind)
        elif '<div class="card-inner">' in data:  # Page loaded successfully
            logging.info(f'Card game available. Picking card {ind}...')
            soup = BeautifulSoup(data, 'html.parser')  # Parse response text as HTML object
            c_type = soup.find('div', class_='card-inner').p.img['src'][-10:-9]
            t_id = soup.find(id='id_initial_token')['value']
            r = self.sess.post('https://p.eagate.573.jp/game/bemani/wbr2020/01/card_save.html', data={  # Pick card ind
                'c_type': c_type,
                'c_id': ind,
                't_id': t_id
            })
            data = r.text
            soup = BeautifulSoup(data, 'html.parser')
            win = '3' in soup.find('div', class_='card-result', id='card').div.em.string
            logging.info(f'You {"won" if win else "lost"}. '
                         f'You now have {self.get_stamp_count(reload=False, cache=data)} stamp(s).')

    def get_stamp_count(self, reload=True, cache=''):
        if not self.success:  # Check if logged in successfully
            return
        data = self.visit_card_page() if reload else cache
        if 'maintenance' in data:  # If eagate is undergoing maintenance
            return 0
        soup = BeautifulSoup(data, 'html.parser')  # Parse response text as HTML object
        return soup.find('div', class_='stamp-num').div.find_all('p')[1].strong.string

    def visit_card_page(self):
        r = self.sess.get('https://p.eagate.573.jp/game/bemani/wbr2020/01/card.html')  # Go to card page
        return r.text

    def onexit(self, _, __):
        logging.info('SIGINT/SIGTERM detected. Exiting...')
        self.close()

    def close(self):
        if not self.running:
            return
        self.running = False
        self.sess.close()
