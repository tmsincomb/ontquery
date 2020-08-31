import json
from typing import Callable, Union, Dict, List, Tuple

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from yarl import URL

from pyontutils.utils import Async, deferred


class InterlexSession:
    """ Boiler plate for SciCrunch server responses. """

    class Error(Exception):
        """Script could not complete."""

    class IncorrectAPIKeyError(Error):
        """Incorrect API key for scicrunch website used."""

    class ServerMessage(Error):
        """Server tailored error message json object."""

    def __init__(self,
                 key: str,
                 scheme: str = 'https',
                 host: str = 'test3.scicrunch.org',
                 auth: Tuple[str, str] = ('', ''),
                 retries: int = 3,
                 backoff_factor: float = 1.0,
                 status_forcelist: tuple = (400, 500, 502, 504),):
        """ Initialize Session with SciCrunch Server.

        :param str key: API key for SciCrunch [should work for test hosts].
        :param str host: Base url for hosting server (can take localhost:8080). Default: 'test3.scicrunch.org'
        :param auth: user, password for authentication. Default: ('', '')
        :param int retries: Number of API retries if code is in status_forcelist. Default: 3
        :param backoff_factor: Delay until next retry in seconds. default (1.0 seconds)
        :param status_forcelist: Status codes that will trigger a retry.
        """
        self.key = key
        # Setup API url #
        self.api = URL(host)
        if not self.api.is_absolute():
            self.api = URL.build(scheme=scheme, host=host)
        self.api = self.api.with_path('api/1')
        # Setup Retries #
        self.session = requests.Session()
        self.session.auth = auth  # legacy; InterLex no longer needs this.
        self.session.headers.update({'Content-type': 'application/json'})
        # retry = Retry(
        #     total=retries,
        #     read=retries,
        #     connect=retries,
        #     backoff_factor=backoff_factor,
        #     status_forcelist=status_forcelist,
        # )
        # adapter = HTTPAdapter(max_retries=retry)
        # self.session.mount('http://', adapter)
        # self.session.mount('https://', adapter)
        # Validate API key & get User ID #
        self.user_id = self._get('user/info').json()['data']['id']

    def __prepare_data(self, data: dict) -> str:
        """ Makes sure request parameters are correct type & contain API key.

        :param data: Parameters for API request.
        """
        data = data or {}
        data.update({'key': self.key})
        data = json.dumps(data)  # Incase backend is missing this step.
        return data

    def __check_response(self, resp: Response) -> None:
        """ Pass, log or break based on response code.

            200  : LOG   : If req was a duplicate from the API key
            201  : PASS  : If req was add/updated/removed successfully
            400+ : BREAK : Your bad
            500+ : BREAK : Our bad

        :param resp: Server response from request.
        """
        if resp.status_code == 401:
            raise self.IncorrectAPIKeyError(f'api_key given is incorrect for url {resp.url}')
        if resp.json().get('errormsg'):
            raise self.ServerMessage(f"\nERROR CODE: [{resp.status_code}]\nSERVER MESSAGE: [{resp.json()['errormsg']}]")
        # resp.raise_for_status()

    def _get(self, endpoint: str, params: dict = None) -> Response:
        """ Quick GET for InterLex.

        :param str endpoint: tail of endpoint (ie term/add).
        :param dict params: params/data for API request.
        :returns: GET server response

        >>>self._get('user/info')
        """
        url = self.api / endpoint
        params = self.__prepare_data(params)  # adds api key to params here
        # noinspection PyTypeChecker
        resp = self.session.get(url, data=params)
        self.__check_response(resp)
        return resp

    def _post(self, endpoint: str, data: dict = None) -> Response:
        """ Quick POST for InterLex.

        :param str endpoint: tail of endpoint (ie term/add).
        :param dict data: params/data for API request.
        :returns: POST server response

        >>>self._post('term/add-simplified', data={'label': 'MyLabel', 'type': 'term'})
        """
        url = self.api / endpoint
        data = self.__prepare_data(data)  # adds api key to data here
        # noinspection PyTypeChecker
        resp = self.session.post(url, data=data)
        self.__check_response(resp)
        return resp

    @staticmethod
    def boost(func: Callable,
              kwargs_list: List[dict],
              batch_size: int = 3,
              rate: int = None) -> iter:
        """ Async boost for Function/Method & list of kwarg params for Function/Method.

        :param func: Function/Method to be asynchronously called.
        :param kwargs_list: Function/Method perameters for each call.
        :param batch_size: Batch size. Default 3
        :param rate: Inner batch size. Auto set to max possible.
        :returns: Generator of repsonses from func.

        >>>from ontquery.plugins.services.interlex_client import InterLexClient
        >>>ilx_cli = InterLexClient(base_url='https://test3.scicrunch.org/api/1/')
        >>>kwargs_list = [{'label': 'Label 1', 'type': 'term'}, {'label': 'Label 2', 'type': 'term'}]
        >>>self.boost(ilx_cli.add_entity, kwargs_list)
        """
        # InterLex specific batch size range #
        # if batch_size > 20:
        #     batch_size = 20  # trust me; this is MAX. Anymore freaks out the php workers.
        if batch_size < 2:
            batch_size = 2  # Any less than 3 and async isn't worth it.
        print('batch size ->', batch_size)
        # Worker #
        gin = lambda kwargs: func(**kwargs)
        # Builds futures dynamically #
        results = []
        for step in range(0, len(kwargs_list), batch_size):
            print('Step ->', step)
            results += Async(rate=rate)(deferred(gin)(kwargs) for kwargs in kwargs_list[step:step+batch_size])
        return results