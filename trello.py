import base64

import requests
from config import TRELLO_KEY
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Trello:
    _URL_PREFIX = 'https://api.trello.com'
    _URL_QUERYSTRING = {'key': TRELLO_KEY, 'token': ''}

    def __init__(self, token):
        self.auth_token = token
        self._URL_QUERYSTRING['token'] = self.auth_token

    def _make_request(self, path, method='GET', querystring=None,
                      payload=None, files=None):
        url = self._URL_PREFIX + path
        call_params = {}
        if querystring is None:
            call_params['params'] = {**self._URL_QUERYSTRING}
        else:
            call_params['params'] = {**self._URL_QUERYSTRING, **querystring}
        if payload is not None:
            call_params['data'] = payload
        if files is not None:
            call_params['files'] = files
        r = requests.request(method, url, **call_params)
        if r.status_code == 200:
            return r.json()
        else:
            logger.debug("Failed call ({}): {}".format(r.status_code, r.text))
            return None

    def get_starred_boards(self):
        j = self._make_request('/1/members/me/boards')
        if j is None:
            return None
        results = {}
        for board in j:
            if board['starred']:
                results[board['id']] = {'name': board['name'], 'id': board['id']}
        return results

    def get_board_info(self, board_id):
        j = self._make_request('/1/boards/{idBoard}'.format(idBoard=board_id))
        return j

    def get_board_lists(self, board_id):
        j = self._make_request('/1/boards/{idBoard}/lists'.format(idBoard=board_id))
        if j is None:
            return None
        results = {}
        for l in j:
            if not l['closed']:
                results[l['id']] = {'name': l['name'], 'id': l['id']}
        return results

    def get_board_cards(self, board_id):
        return self._make_request('/1/boards/{idBoard}/cards'.format(idBoard=board_id))

    def get_list_cards(self, list_id):
        return self._make_request('/1/lists/{idList}/cards'.format(idList=list_id))

    def create_list_in_board(self, list_name, board_id):
        j = self._make_request('/1/lists', method='POST',
                               querystring={"name": list_name,
                                            "idBoard": board_id,
                                            "pos": "bottom"})
        if j is None:
            return None
        return j['id']

    def remove_cover(self, card_id):
        url = '/1/cards/{}'.format(card_id)
        querystring = {'idAttachmentCover': 'null'}
        j = self._make_request(url, method='PUT',
                               querystring=querystring)
        return j

    def create_card_in_list(self, list_id, card_name, content, content_type='text'):
        url = '/1/cards'
        querystring = {
            'idList': list_id,
            'name': card_name,
            'pos': 'top'
        }

        if content_type == 'text':
            querystring['desc'] = content
        elif content_type == 'url':
            soup = BeautifulSoup(requests.get(content).text, 'lxml')
            title = soup.find_all('title')[0]
            querystring['desc'] = content
            querystring['name'] = title
            # querystring['urlSource'] = content

        j = self._make_request(url, method='POST',
                               querystring=querystring)
        if j is None:
            return None
        card_id = j['id']

        if content_type == 'text':
            return card_id

        if content_type == 'image':
            url = '/1/cards/{}/attachments'.format(card_id)
            files = {'file': requests.get(content).content}
            _ = self._make_request(url, method='POST',
                                   files=files)

        if content_type == 'url':
            url = '/1/cards/{}/attachments'.format(card_id)
            querystring = {'url': content, 'idAttachmentCover': 'null'}
            _ = self._make_request(url, method='POST',
                                   querystring=querystring)

        if (content_type == 'url') | (content_type == 'image'):
            _ = self.remove_cover(card_id)

        return card_id

        # extension = content.split(".")[-1]
        # filename = card_name
        # querystring['fileSource'] = "data:image/{extension};" \
        #                             "name={filename};base64,".format(extension=extension,
        #                                                              filename=filename) + \
        #                             base64.b64encode(requests.get(content).content).decode()[:1000]

