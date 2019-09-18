import json
import os
from typing import Union, List
from elasticsearch import Elasticsearch
from fuzzywuzzy import fuzz
import requests
from ontquery.utils import log
es = Elasticsearch()

class InterLexClient:

    """ Connects to SciCrunch via its' api endpoints

    Purpose is to allow external curators to add entities and annotations to
    those entities.

    Functions To Use:
        add_entity
        add_annotation

    Notes On Time Complexity:
        Function add_entity, if added an entity successfully, will hit a
        least 5 endpoints. This may cause it to take a few seconds to load
        each entity into SciCrunch. Function add_annotation is a little more
        forgiving with it only hitting 3 minimum.
    """
    class Error(Exception):
        """Script could not complete."""

    class SuperClassDoesNotExistError(Error):
        """The superclass listed does not exist!"""

    class EntityDoesNotExistError(Error):
        """The entity listed does not exist!"""

    class AlreadyExistsError(Error):
        """The entity listed already exists!"""

    class BadResponseError(Error):
        """Response did not return a 200s status."""

    class NoLabelError(Error):
        """Need label for new entity."""

    class NoTypeError(Error):
        """New Entities need a type given."""

    class MissingKeyError(Error):
        """Missing dict key for scicrunch entity for API endpoint used."""

    class IncorrectKeyError(Error):
        """Incorrect possible dictionary key for scicrunch entity."""

    class IncorrectAPIKeyError(Error):
        """Incorrect API key for scicrunch website used."""

    class IncorrectAuthError(Error):
        """Incorrect authentication key for testing websites."""

    default_base_url = 'https://scicrunch.org/api/1/'
    ilx_base_url = 'http://uri.interlex.org/base/'

    def __init__(self, base_url: str = default_base_url):
        """Short summary.

        :param str base_url: . Defaults to default_base_url.
        """
        self.base_url = base_url
        self.api_key = os.environ.get(
            'INTERLEX_API_KEY', os.environ.get('SCICRUNCH_API_KEY', None))
        self._kwargs = {}
        if 'test' in base_url:
            auth = os.environ.get('SCICRUNCH_TEST_U'), os.environ.get(
                'SCICRUNCH_TEST_P')
            if not auth[0] or not auth[1]:
                raise self.IncorrectAuthError(
                    'TEST needs a user & password to get into '
                    'https://test[0-9].scicrunch.org.\n'
                    'Add them to ~/.bashrc as so:\n'
                    'export SCICRUNCH_TEST_U=put_user_here\n'
                    'export SCICRUNCH_TEST_P=put_password_here'
                )
            self.api_key = os.environ.get(
                'INTERLEX_API_KEY_TEST', os.environ.get(
                    'SCICRUNCH_API_KEY_TEST', None))
            if not self.api_key:
                raise self.IncorrectAPIKeyError(
                    'TEST api_key not found. Please go to '
                    'https://test.scicrunch.org/ '
                    'and get an api_key. Add it to ~/.basrc as so \n'
                    'export SCICRUNCH_API_KEY_TEST=your_api_key_here'
                )
            self._kwargs['auth'] = auth

        user_info_url = self.base_url + 'user/info?key=' + self.api_key
        self.check_api_key(user_info_url)
        self.user_id = str(self.get(user_info_url)['id'])

    def check_api_key(self, url: str) -> None:
        """Resquests user info to check if user exists and has validation.

        :param type url: API endpoint to request user info.
        :return: None
        :rtype: None
        :raises IncorrectAPIKeyError keyError: raises Error
        """
        response = requests.get(
            url,
            headers={'Content-type': 'application/json'},
            **self._kwargs
        )
        if response.status_code not in [200, 201]:  # Safety catch.
            sec = url.replace(self.api_key, '[secure]')
            raise self.IncorrectAPIKeyError(
                f'api_key given is incorrect. {sec}')

    def process_response(self,
                         response: requests.models.Response,
                         params: dict = None) -> dict:
        """Checks for correct data response and status codes.

        :param requests.models.Response response: requests get/post output.
        :param dict params: requests get/post params input.
        :return: single scicrunch entity in dict format.
        :rtype: dict
        """
        if params:
            params = {k:v for k, v in params.items() if k != 'api_key'}
        try:
            output = response.json()
        except json.JSONDecodeError:  # Server is having a bad day and crashed.
            raise self.BadResponseError(
                f'\nError: Json could not returned\n'
                f'Status Code: [{response.status_code}]\n'
                f'Params: {params}\n'
                f'Url: {response.url}\n'
                f'Output: {response.text}')

        if response.status_code in [200, 201]:
            pass
        elif response.status_code == 400:  # Builtin Bad Request
            return output
        else:  # Safety catch.
            raise self.BadResponseError(
                f'\nError: Unknown\n'
                f'Status Code: [{response.status_code}]\n'
                f'Params: {params}\n'
                f'Url: {response.url}\n'
                f'Output: {response.text}')

        return output['data']

    def get(self,
            url: str,
            params: dict = None,
            auth: tuple = ()) -> Union[list, dict]:
        """Get Requests tailored for SciCrunch database response.

        :param str url: Any scicrunch API get endpoint url.
        :param dict params: API endpoint needs/options. Defaults to {}.
        :return: Entity dict or list of Entity dicts.
        :rtype: Union[list, dict]
        """
        # TODO: need to deal with _kwargs. bad practice
        auth = auth if auth else self._kwargs.get('auth')
        response = requests.get(
            url,
            headers={'Content-type': 'application/json'},
            params=params,
            auth=auth,
        )
        # Deduce possible errors and extract possible output
        output = self.process_response(response=response, params=params)
        return output

    def post(self, url: str, data: dict) -> Union[list, dict]:
        """Post Request tailored to SciCrunch Databases.

        :param str url: SciCrunch API endpoint to Add/Mod/Del Entity.
        :param dict data: Entity's metadata you wish to Add/Mod/Del.
        :return: Entity dict or list of Entity dicts.
        :rtype: Union[list, dict]
        """
        data.update({
            'key': self.api_key,
        })
        response = requests.post(
            url,
            # Elastic takes in dict while other apis need a string...
            # Yeah I know...
            data=json.dumps(data) if 'elastic' not in url else data,
            headers={'Content-type': 'application/json'},
            **self._kwargs
        )
        output = self.process_response(response)
        return output

    def fix_ilx(self, ilx_id: str) -> str:
        """Database only excepts lower case and underscore version of ID.

        :param str ilx_id: Intended.
        :return: .
        :rtype: str

        >>>fix_ilx('http://uri.interlex.org/base/ilx_0101431')
        ilx_0101431
        >>>fix_ilx('ILX:ilx_0101431')
        ilx_0101431
        """
        # Incase of url pass through
        ilx_id = ilx_id.rsplit('/', 1)[-1]
        # Easiest way to check if it was intended to be an InterLex entity ID
        if ilx_id[:4] not in ['TMP:', 'tmp_', 'ILX:', 'ilx_']:
            raise ValueError(
                f"Provided ID {ilx_id} couldn't be determined as InterLex ID.")
        return ilx_id.replace('ILX:', 'ilx_').replace('TMP:', 'tmp_')

    def process_superclass(self, entity: List[dict]) -> List[dict]:
        """Replaces ILX ID with superclass ID."""
        superclass = entity.pop('superclass')
        label = entity['label']
        if not superclass.get('ilx_id'):
            raise self.SuperClassDoesNotExistError(
                f'Superclass not given an interlex ID for label: {label}')
        superclass_data = self.get_entity(superclass['ilx_id'])
        if not superclass_data['id']:
            raise self.SuperClassDoesNotExistError(
                'Superclass ILX ID: ' + superclass['ilx_id'] + ' does not exist in SciCrunch')
        # BUG: only excepts superclass_tid
        entity['superclasses'] = [{'superclass_tid': superclass_data['id']}]
        return entity

    def process_synonyms(self, entity: List[dict]) -> List[dict]:
        """ Making sure key/value is in proper format for synonyms in entity
        """
        label = entity['label']
        for synonym in entity['synonyms']:
            # these are internal errors and users should never see them
            if 'literal' not in synonym:
                raise ValueError(
                    f'Synonym not given a literal for label: {label}')
            if len(synonym) > 1:
                raise ValueError(
                    f'Too many keys in synonym for label: {label}')
        return entity

    def process_existing_ids(self, entity: List[dict]) -> List[dict]:
        """Making sure existing_id items are in proper format for entity."""
        label = entity['label']
        existing_ids = entity['existing_ids']
        for existing_id in existing_ids:
            if 'curie' not in existing_id or 'iri' not in existing_id:
                raise ValueError(
                    f'Missing needing key(s) in existing_ids '
                    f'for label: {label}')
            if len(existing_id) > 2:
                raise ValueError(
                    f'Extra keys not recognized in existing_ids '
                    f'for label: {label}')
        return entity

    def query_elastic(self,
                      term: str = None,
                      label: str = None,
                      body: dict = None,
                      **kwargs) -> List[dict]:
        """ Queries Elastic for term (wild card) or raw query to elastic.

        If you choose to do a label search you need Elasticsearch:
        > SCICRUNCH_ELASTIC_URL: core elastic search url (no indexes)
        > SCICRUNCH_ELASTIC_USER: username
        > SCICRUNCH_ELASTIC_PASSWORD: password
        within your bashrc. The reason is the API endpoint in SciCrunch cannot
        be customized at all and it is just for a general search.

        :param str term: wild card value to be searched throughout entities.
        :param str label: direct exact matching for label field.
        :param dict body: raw query for elastic where {"query":{?}} is input.
            WARNING, your query value should be lowercase and cleaned. Elastic
            doesn't clean input by default...
            Maybe a nice addition to look into?
        :returns: list of all possible entity hits in their nested dict format.
        :rtype: List[dict]

        # Say we want "brain" entity.
        >>>query_elastic(term='brains') # random results
        >>>query_elastic(kabel='Brains') # will actually get you brain
        # Returns [], but this is just to show the format of body field.
        >>>query_elastic(body={"query": {"match": {'label':'brains'}}})
        # Therefore if you are interested in "real" hits use label
        # or custom body field.
        """
        if label or body:
            try:
                url = os.environ.get('SCICRUNCH_ELASTIC_URL') + '/interlex'
            except:
                raise ValueError(
                    'SCICRUNCH_ELASTIC_URL need to be in ~/.bashrc.')
            user = os.environ.get('SCICRUNCH_ELASTIC_USER')
            password = os.environ.get('SCICRUNCH_ELASTIC_PASSWORD')
            if not user or not password:
                raise ValueError(
                    'SCICRUNCH_ELASTIC_USER & SCICRUNCH_ELASTIC_PASSWORD'
                    'need to be in ~/.bashrc.')
            es = Elasticsearch(url, http_auth=(user, password))
            # Favor label over body
            if label:
                # elastic perfers input to be clean
                label = label.lower().strip()
                body = {
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "fuzzy": {
                                        "label": {
                                            "value": label,
                                            "fuzziness": 1
                                            }
                                        }
                                    },
                                {
                                    "match": {
                                        "label": {
                                            "query": label,
                                            "boost": 100
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "size": 3,
                    "from": 0
                }
            else:
                pass
            hits = es.search(index="term", body=body)['hits']['hits']
        else:
            url = self.base_url + 'term/elastic/search'
            params = {
                'term': term,
                'key': self.api_key,
                **kwargs,
            }
            hits = self.get(
                url,
                params=params,
            )['hits']['hits']
        if hits:
            hits = [hit['_source'] for hit in hits]
            for hit in hits:
                # For QueryResult
                hit['iri'] = 'http://uri.interlex.org/base/' + hit['ilx']
                hit['curie'] = hit['ilx'].replace(
                    'ilx_', 'ILX:').replace('tmp_', 'TMP:')

        return hits

    def crude_search_scicrunch_via_label(self, label: str) -> dict:
        """Server returns anything that is simlar in any catagory."""
        url = self.base_url + 'term/search/{term}?key={api_key}'.format(
            term=label,
            api_key=self.api_key,
        )
        return self.get(url)

    def query_elastic_with_confidence(self,
                                      term: str,
                                      confidence: int = 85,
                                      **kwargs) -> List[dict]:
        """Search SciCrunch for Loosely matched Terms.

        We don't trust elastic up front because it scores on the total entity.
        All we care about is the match quality on on a single value. Fuzzy will
        check each value on dict and with return a score from the best matched
        value in said dict. Elastic also gives the top results even if they are
        bad. We need a quality control for curators, hence this function.

        :param str term: Any value that defines SciCrunch Entity searched.
        :param int confidence: Match similarity btw 0-100. Defaults to 85.
        :param type **kwargs: Params for Elastcsearch Query.
        :return: List of all possibly matched Entities.
        :rtype: List[dict]

        >>>query_elastic_with_confidence(term='brain', confidence=95)
        """
        query = {
            'term': term,
            'from': '0',  # elastic doesnt always start at 0 unless given
            'size': '10',  # limit
            'fields': ['label'],
            **kwargs,
        }
        elastic_hits = self.query_elastic(**query)

        # TODO: This would be cool to do if i figured out how to override processor to except dict choices properly
        # compares each choice
        # elastic_hits = process.extract(
        #     query = term,
        #     choices = elastic_hits,
        #     # compares each element individually & orderring doesnt matter
        #     # EXAMPLE: 'Life Is Good' == 'good is life'
        #     scorer=fuzz.token_sort_ratio,
        #     limit=None # default is 5
        # )

        # Compares each element individually where ordering doesnt matter
        # & only returns matches with >= confidence score
        matches = [hit for hit in elastic_hits if fuzz.token_sort_ratio(
            hit['label'], term) >= confidence]
        return matches

    def check_scicrunch_for_label(self, label: str) -> dict:
        """Check label with your user ID already exists.

        There are can be multiples of the same label in interlex, but there
        should only be one label with your user id. Therefore you can create
        labels if there already techniqually exist, but not if you are the
        one to create it.

        Args:
            label (str): label related to the entity you want to search

        Returns:
            dictionary of scicrunch fields for a single exact matched entity
        """
        list_of_crude_matches = self.crude_search_scicrunch_via_label(label)
        for crude_match in list_of_crude_matches:
            # If labels match
            if crude_match['label'].lower().strip() == label.lower().strip():
                complete_data_of_crude_match = self.get_entity(
                    crude_match['ilx'])
                # crude_match_label = crude_match['label']
                crude_match_user_id = complete_data_of_crude_match['uid']
                # If label was created by you
                if str(self.user_id) == str(crude_match_user_id):
                    # You created the entity already
                    return complete_data_of_crude_match
        # No label AND user id match
        return {}

    def get_entity(self, ilx_id: str, iri_curie: bool = False) -> dict:
        """Get full Entity metadata from its ILX ID.

        (expect their annotations and relationships)

        :param str ilx_id: ILX ID of current Entity.
        :param bool iri_curie: . Defaults to False.
        """
        ilx_id = self.fix_ilx(ilx_id)
        url = self.base_url + f"ilx/search/identifier/{ilx_id}"
        resp = self.get(
            url,
            params={'key': self.api_key}
        )
        # work around for ontquery.utils.QueryResult input
        if iri_curie:
            resp['iri'] = 'http://uri.interlex.org/base/' + resp['ilx']
            resp['curie'] = resp['ilx'].replace(
                'ilx_', 'ILX:').replace('tmp_', 'TMP:')
        return resp

    def add_entity(self,
                   label: str,
                   type: str,
                   definition: str = None,
                   comment: str = None,
                   superclass: str = None,
                   synonyms: list = None) -> dict:
        """Short summary.

        :param str label: .
        :param str type: .
        :param str definition: . Defaults to None.
        :param str comment: . Defaults to None.
        :param str superclass: . Defaults to None.
        :param list synonyms: . Defaults to None.
        :return: .
        :rtype: dict
        """
        template_entity_input = {k: v for k,
                                 v in locals().items() if k != 'self' and v}
        if template_entity_input.get('superclass'):
            template_entity_input['superclass'] = self.fix_ilx(
                template_entity_input['superclass'])

        if not label:
            raise self.NoLabelError('Entity needs a label')
        if not type:
            raise self.NoTypeError('Entity needs a type')

        entity_input = {
            'label': label,
            'type': type,
        }

        if definition:
            entity_input['definition'] = definition

        if comment:
            entity_input['comment'] = comment

        if superclass:
            entity_input['superclass'] = {'ilx_id': self.fix_ilx(superclass)}

        if synonyms:
            entity_input['synonyms'] = [{'literal': syn} for syn in synonyms]

        raw_entity_outout = self.add_raw_entity(entity_input)

        # Sanity check -> output same as input, but filled with response data
        entity_output = {}
        ics = [(e['iri'], e['curie'])
               for e in raw_entity_outout['existing_ids']]
        entity_output['iri'], entity_output['curie'] = sorted((i, c)
                                                              for i, c in ics
                                                              if 'ilx_' in i)[0]
        ### FOR NEW BETA. Old can have 'ilx_' in the ids ###
        if 'tmp' in raw_entity_outout['ilx']:
            _id = raw_entity_outout['ilx'].split('_')[-1]
            entity_output['iri'] = 'http://uri.interlex.org/base/tmp_' + _id
            entity_output['curie'] = 'TMP:' + _id

        for key, value in template_entity_input.items():
            if key == 'superclass':
                entity_output[key] = raw_entity_outout['superclasses'][0]['ilx']
            elif key == 'synonyms':
                entity_output[key] = [syn['literal']
                                      for syn in raw_entity_outout['synonyms']]
            else:
                entity_output[key] = str(raw_entity_outout[key])

        # skip this for now, I check it downstream be cause I'm paranoid, but in this client it is
        # safe to assume that the value given will be the value returned if there is a return at all
        # it also isn't that they match exactly, because some new values (e.g. iri and curie) are expected
        #if entity_output != template_entity_input:
            # DEBUG: helps see what's wrong; might want to make a clean version of this
            # for key, value in template_entity_input.items():
            #     if template_entity_input[key] != entity_output[key]:
            #         print(template_entity_input[key], entity_output[key])
            #raise self.BadResponseError('The server did not return proper data!')

        if entity_output.get('superclass'):
            entity_output['superclass'] = self.ilx_base_url + \
                entity_output['superclass']
        entity_output['ilx'] = self.ilx_base_url + raw_entity_outout['ilx']

        return entity_output

    def add_raw_entity(self, entity: dict) -> dict:
        """ Adds entity if it does not already exist under your user ID.

            Need to provide a list of dictionaries that have at least the key/values
            for label and type. If given a key, the values provided must be in the
            format shown in order for the server to except them. You can input
            multiple synonyms, or existing_ids.

            Entity type can be any of the following: term, pde, fde, cde, annotation, or relationship

            Options Template:
                entity = {
                    'label': '',
                    'type': '',
                    'definition': '',
                    'comment': '',
                    'superclass': {
                        'ilx_id': ''
                    },
                    'synonyms': [
                        {
                            'literal': ''
                        },
                    ],
                    'existing_ids': [
                        {
                            'iri': '',
                            'curie': '',
                        },
                    ],
                }

            Minimum Needed:
                entity = {
                    'label': '',
                    'type': '',
                }

            Example:
                entity = {
                    'label': 'brain',
                    'type': 'pde',
                    'definition': 'Part of the central nervous system',
                    'comment': 'Cannot live without it',
                    'superclass': {
                        'ilx_id': 'ilx_0108124', # ILX ID for Organ
                    },
                    'synonyms': [
                        {
                            'literal': 'Encephalon'
                        },
                        {
                            'literal': 'Cerebro'
                        },
                    ],
                    'existing_ids': [
                        {
                            'iri': 'http://uri.neuinfo.org/nif/nifstd/birnlex_796',
                            'curie': 'BIRNLEX:796',
                        },
                    ],
                }
        """

        needed_in_entity = set([
            'label',
            'type',
        ])
        options_in_entity = set([
            'label',
            'type',
            'definition',
            'comment',
            'superclass',
            'synonyms',
            'existing_ids'
        ])
        prime_entity_url = self.base_url + 'ilx/add'
        add_entity_url = self.base_url + 'term/add'

        ### Checking if key/value format is correct ###
        # Seeing if you are missing a needed key
        if (set(entity) & needed_in_entity) != needed_in_entity:
            raise self.MissingKeyError(
                'You need key(s): ' + str(needed_in_entity - set(entity)))
        # Seeing if you have other options not included in the description
        elif (set(entity) | options_in_entity) != options_in_entity:
            raise self.IncorrectKeyError(
                'Unexpected key(s): ' + str(set(entity) - options_in_entity))
        # BUG: server only takes lowercase
        entity['type'] = entity['type'].lower()
        if entity['type'] not in ['term', 'relationship', 'annotation', 'cde', 'fde', 'pde']:
            raise TypeError(
                'Entity should be one of the following: '
                + 'term, relationship, annotation, cde, fde, pde')
        if entity.get('superclass'):
            entity = self.process_superclass(entity)
        if entity.get('synonyms'):
            entity = self.process_synonyms(entity)
        if entity.get('existing_ids'):
            entity = self.process_existing_ids(entity)
        entity['uid'] = self.user_id  # BUG: php lacks uid update

        ### Adding entity to SciCrunch ###
        entity['term'] = entity.pop('label')  # ilx/add nuance
        ilx_data = self.post(
            url=prime_entity_url,
            data=entity.copy(),
        )  # requesting spot in server for entity
        if ilx_data.get('ilx'):
            ilx_id = ilx_data['ilx']
        else:
            ilx_id = ilx_data['fragment']  # beta.scicrunch.org
        entity['label'] = entity.pop('term')  # term/add nuance
        entity['ilx'] = ilx_id  # need entity ilx_id to place entity in db

        output = self.post(
            url=add_entity_url,
            data=entity.copy(),
        )  # data represented in SciCrunch interface

        ### Checking if label already exisits ###
        if output.get('errormsg'):
            if 'already exists' in output['errormsg'].lower():
                prexisting_data = self.check_scicrunch_for_label(
                    entity['label'])
                if prexisting_data:
                    log.warning(
                        'You already added entity ' + entity['label'] + '\n'
                        'with ILX ID: ' + prexisting_data['ilx'])
                    return prexisting_data

                self.Error(output)  # FIXME what is the correct error here?

            self.Error(output)  # FIXME what is the correct error here?

        # BUG: server output incomplete compared to search via ilx ids
        output = self.get_entity(output['ilx'])

        return output

    def update_entity(
            self,
            ilx_id: str,
            label: str = None,
            type: str = None,
            definition: str = None,
            comment: str = None,
            superclass: str = None,
            synonyms: list = None) -> dict:
        """ Updates pre-existing entity as long as the api_key is from the account that created it

            Args:
                label: name of entity
                type: entities type
                    Can be any of the following: term, cde, fde, pde, annotation, relationship
                definition: entities definition
                comment: a foot note regarding either the interpretation of the data or the data itself
                superclass: entity is a sub-part of this entity
                    Example: Organ is a superclass to Brain
                synonyms: entity synonyms

            Returns:
                Server response that is a nested dictionary format
        """

        template_entity_input = {k: v for k,
                                 v in locals().copy().items() if k != 'self'}
        if template_entity_input.get('superclass'):
            template_entity_input['superclass'] = self.fix_ilx(
                template_entity_input['superclass'])

        existing_entity = self.get_entity(ilx_id=ilx_id)
        # TODO: Need to make a proper ilx_id check error
        if not existing_entity['id']:
            raise self.EntityDoesNotExistError(
                f'ilx_id provided {ilx_id} does not exist')

        update_url = self.base_url + \
            'term/edit/{id}'.format(id=existing_entity['id'])

        if label:
            existing_entity['label'] = label

        if type:
            existing_entity['type'] = type

        if definition:
            existing_entity['definition'] = definition

        if comment:
            existing_entity['comment'] = comment

        if superclass:
            existing_entity['superclass'] = {'ilx_id': superclass}
            existing_entity = self.process_superclass(existing_entity)

        # If a match use old data, else append new synonym
        if synonyms:
            if existing_entity['synonyms']:
                new_existing_synonyms = []
                existing_synonyms = {syn['literal'].lower(
                ): syn for syn in existing_entity['synonyms']}
                for synonym in synonyms:
                    existing_synonym = existing_synonyms.get(synonym.lower())
                    if not existing_synonym:
                        new_existing_synonyms.append({'literal': synonym})
                    else:
                        new_existing_synonyms.append(existing_synonym)
                existing_entity['synonyms'] = new_existing_synonyms

        # Just in case I need this...
        # if synonyms_to_delete:
        #     if existing_entity['synonyms']:
        #         remaining_existing_synonyms = []
        #         existing_synonyms = {syn['literal'].lower():syn for syn in existing_entity['synonyms']}
        #         for synonym in synonyms:
        #             if existing_synonyms.get(synonym.lower()):
        #                 existing_synonyms.pop(synonym.lower())
        #             else:
        #                 print('WARNING: synonym you wanted to delete', synonym, 'does not exist')
        #         existing_entity['synonyms'] = list(existing_synonyms.values())

        response = self.post(
            url=update_url,
            data=existing_entity,
        )

        # BUG: server response is bad and needs to actually search again to get proper format
        raw_entity_outout = self.get_entity(response['ilx'])

        entity_output = {}
        ics = [(e['iri'], e['curie'])
               for e in raw_entity_outout['existing_ids']]
        entity_output['iri'], entity_output['curie'] = sorted((i, c)
                                                              for i, c in ics
                                                              if 'ilx_' in i)[0]
        ### FOR NEW BETA. Old can have 'ilx_' in the ids ###
        if 'tmp' in raw_entity_outout['ilx']:
            _id = raw_entity_outout['ilx'].split('_')[-1]
            entity_output['iri'] = 'http://uri.interlex.org/base/tmp_' + _id
            entity_output['curie'] = 'TMP:' + _id

        log.info(template_entity_input)
        for key, value in template_entity_input.items():
            if key == 'superclass':
                if raw_entity_outout.get('superclasses'):
                    entity_output[key] = raw_entity_outout['superclasses'][0]['ilx']
            elif key == 'synonyms':
                entity_output[key] = [syn['literal']
                                      for syn in raw_entity_outout['synonyms']]
            elif key == 'ilx_id':
                pass
            else:
                entity_output[key] = str(raw_entity_outout[key])

        if entity_output.get('superclass'):
            entity_output['superclass'] = self.ilx_base_url + \
                entity_output['superclass']
        entity_output['ilx'] = self.ilx_base_url + raw_entity_outout['ilx']

        return entity_output

    def get_annotation_via_tid(self, tid: str) -> dict:
        """ Gets annotation via anchored entity id """
        url = self.base_url + 'term/get-annotations/{tid}?key={api_key}'.format(
            tid=tid,
            api_key=self.api_key,
        )
        return self.get(url)

    def add_annotation(
            self,
            term_ilx_id: str,
            annotation_type_ilx_id: str,
            annotation_value: str) -> dict:
        """ Adding an annotation value to a prexisting entity

        An annotation exists as 3 different parts:
            1. entity with type term, cde, fde, or pde
            2. entity with type annotation
            3. string value of the annotation

        Example:
            annotation = {
                'term_ilx_id': 'ilx_0101431', # brain ILX ID
                'annotation_type_ilx_id': 'ilx_0381360', # hasDbXref ILX ID
                'annotation_value': 'http://neurolex.org/wiki/birnlex_796',
            }
        """
        url = self.base_url + 'term/add-annotation'

        term_data = self.get_entity(term_ilx_id)
        if not term_data['id']:
            raise self.EntityDoesNotExistError(
                'term_ilx_id: ' + term_ilx_id + ' does not exist'
            )
        anno_data = self.get_entity(annotation_type_ilx_id)
        if not anno_data['id']:
            raise self.EntityDoesNotExistError(
                'annotation_type_ilx_id: ' + annotation_type_ilx_id
                + ' does not exist'
            )

        data = {
            'tid': term_data['id'],
            'annotation_tid': anno_data['id'],
            'value': annotation_value,
            'term_version': term_data['version'],
            'annotation_term_version': anno_data['version'],
            'orig_uid': self.user_id,  # BUG: php lacks orig_uid update
        }

        output = self.post(
            url=url,
            data=data,
        )

        ### If already exists, we return the actual annotation properly ###
        if output.get('errormsg'):
            if 'already exists' in output['errormsg'].lower():
                term_annotations = self.get_annotation_via_tid(term_data['id'])
                for term_annotation in term_annotations:
                    if str(term_annotation['annotation_tid']) == str(anno_data['id']):
                        if term_annotation['value'] == data['value']:
                            log.warning(
                                'Annotation: [' + term_data['label']
                                + ' -> ' + anno_data['label']
                                + ' -> ' + data['value'] + '], already exists.'
                            )
                            return term_annotation

                raise self.AlreadyExistsError(output)

            raise self.Error(output)

        return output

    def delete_annotation(
            self,
            term_ilx_id: str,
            annotation_type_ilx_id: str,
            annotation_value: str) -> dict:
        """ If annotation doesnt exist, add it
        """

        term_data = self.get_entity(term_ilx_id)
        if not term_data['id']:
            raise self.EntityDoesNotExistError(
                'term_ilx_id: ' + term_ilx_id + ' does not exist'
            )
        anno_data = self.get_entity(annotation_type_ilx_id)
        if not anno_data['id']:
            raise self.EntityDoesNotExistError(
                'annotation_type_ilx_id: ' + annotation_type_ilx_id
                + ' does not exist'
            )

        entity_annotations = self.get_annotation_via_tid(term_data['id'])
        annotation_id = ''

        for annotation in entity_annotations:
            if str(annotation['tid']) == str(term_data['id']):
                if str(annotation['annotation_tid']) == str(anno_data['id']):
                    if str(annotation['value']) == str(annotation_value):
                        annotation_id = annotation['id']
                        break
        if not annotation_id:
            log.warning('Annotation you wanted to delete does not exist')
            return None

        url = self.base_url + 'term/edit-annotation/{annotation_id}'.format(
            annotation_id=annotation_id
        )

        data = {
            'tid': ' ',  # for delete
            'annotation_tid': ' ',  # for delete
            'value': ' ',  # for delete
            'term_version': ' ',
            'annotation_term_version': ' ',
        }

        output = self.post(
            url=url,
            data=data,
        )

        # check output
        return output

    def get_relationship_via_tid(self, tid: str) -> dict:
        url = self.base_url + 'term/get-relationships/{tid}?key={api_key}'.format(
            tid=tid,
            api_key=self.api_key,
        )
        return self.get(url)

    def add_relationship(
            self,
            entity1_ilx: str,
            relationship_ilx: str,
            entity2_ilx: str) -> dict:
        """ Adds relationship connection in Interlex

        A relationship exists as 3 different parts:
            1. entity with type term, cde, fde, or pde
            2. entity with type relationship that connects entity1 to entity2
                -> Has its' own meta data, so no value needed
            3. entity with type term, cde, fde, or pde
        """

        url = self.base_url + 'term/add-relationship'

        entity1_data = self.get_entity(entity1_ilx)
        if not entity1_data['id']:
            raise self.EntityDoesNotExistError(
                'entity1_ilx: ' + entity1_ilx + ' does not exist'
            )
        relationship_data = self.get_entity(relationship_ilx)
        if not relationship_data['id']:
            raise self.EntityDoesNotExistError(
                'relationship_ilx: ' + relationship_ilx + ' does not exist'
            )
        entity2_data = self.get_entity(entity2_ilx)
        if not entity2_data['id']:
            raise self.EntityDoesNotExistError(
                'entity2_ilx: ' + entity2_ilx + ' does not exist'
            )

        data = {
            'term1_id': entity1_data['id'],
            'relationship_tid': relationship_data['id'],
            'term2_id': entity2_data['id'],
            'term1_version': entity1_data['version'],
            'term2_version': entity2_data['version'],
            'relationship_term_version': relationship_data['version'],
            'orig_uid': self.user_id,  # BUG: php lacks orig_uid update
        }

        output = self.post(
            url=url,
            data=data,
        )
        ### If already exists, we return the actual relationship properly ###
        if output.get('errormsg'):
            if 'already exists' in output['errormsg'].lower():
                term_relationships = self.get_relationship_via_tid(
                    entity1_data['id'])
                for term_relationship in term_relationships:
                    if str(term_relationship['term2_id']) == str(entity2_data['id']):
                        if term_relationship['relationship_tid'] == relationship_data['id']:
                            log.warning(
                                'relationship: ['
                                + entity1_data['label'] + ' -> '
                                + relationship_data['label']
                                + ' -> ' + entity2_data['label']
                                + '], already exists.'
                            )
                            return term_relationship
                exit(output)
            exit(output)

        return output

    def delete_relationship(
            self,
            entity1_ilx: str,
            relationship_ilx: str,
            entity2_ilx: str) -> dict:
        """ Adds relationship connection in Interlex

        A relationship exists as 3 different parts:
            1. entity with type term, cde, fde, or pde
            2. entity with type relationship that connects entity1 to entity2
                -> Has its' own meta data, so no value needed
            3. entity with type term, cde, fde, or pde
        """

        entity1_data = self.get_entity(entity1_ilx)
        if not entity1_data['id']:
            raise self.EntityDoesNotExistError(
                'entity1_ilx: ' + entity1_data + ' does not exist'
            )
        relationship_data = self.get_entity(relationship_ilx)
        if not relationship_data['id']:
            raise self.EntityDoesNotExistError(
                'relationship_ilx: ' + relationship_ilx + ' does not exist'
            )
        entity2_data = self.get_entity(entity2_ilx)
        if not entity2_data['id']:
            raise self.EntityDoesNotExistError(
                'entity2_ilx: ' + entity2_data + ' does not exist'
            )

        data = {
            'term1_id': ' ',  # entity1_data['id'],
            'relationship_tid': ' ',  # relationship_data['id'],
            'term2_id': ' ',  # entity2_data['id'],
            'term1_version': entity1_data['version'],
            'term2_version': entity2_data['version'],
            'relationship_term_version': relationship_data['version'],
            'orig_uid': self.user_id,  # BUG: php lacks orig_uid update
        }

        entity_relationships = self.get_relationship_via_tid(
            entity1_data['id'])
        # TODO: parse through entity_relationships to see if we have a match; else print warning and return None

        relationship_id = None
        for relationship in entity_relationships:
            if str(relationship['term1_id']) == str(entity1_data['id']):
                if str(relationship['term2_id']) == str(entity2_data['id']):
                    if str(relationship['relationship_tid']) == str(relationship_data['id']):
                        relationship_id = relationship['id']
                        break

        if not relationship_id:
            log.warning('Annotation you wanted to delete does not exist')
            return {}

        url = self.base_url + \
            'term/edit-relationship/{id}'.format(id=relationship_id)

        output = self.post(
            url=url,
            data=data,
        )

        return output


def examples():
    ''' Examples of how to use. Default are that some functions are commented out in order
        to not cause harm to existing metadata within the database.
    '''
    sci = InterLexClient(
        base_url='https://test.scicrunch.org/api/1/',  # NEVER CHANGE
    )
    entity = {
        'label': 'brain115',
        'type': 'fde',  # broken at the moment NEEDS PDE HARDCODED
        'definition': 'Part of the central nervous system',
        'comment': 'Cannot live without it',
        'superclass': {
            'ilx_id': 'ilx_0108124',  # ILX ID for Organ
        },
        'synonyms': [
            {
                'literal': 'Encephalon'
            },
            {
                'literal': 'Cerebro'
            },
        ],
        'existing_ids': [
            {
                'iri': 'http://uri.neuinfo.org/nif/nifstd/birnlex_796',
                'curie': 'BIRNLEX:796',
            },
        ],
    }
    simple_entity = {
        'label': entity['label'],
        'type': entity['type'],  # broken at the moment NEEDS PDE HARDCODED
        'definition': entity['definition'],
        'comment': entity['comment'],
        'superclass': entity['superclass']['ilx_id'],
        'synonyms': [syn['literal'] for syn in entity['synonyms']],
        'predicates': {'tmp_0381624': 'http://example_dbxref'}
    }
    annotation = {
        'term_ilx_id': 'ilx_0101431',  # brain ILX ID
        'annotation_type_ilx_id': 'tmp_0381624',  # hasDbXref ILX ID
        'annotation_value': 'PMID:12345',
    }
    relationship = {
        'entity1_ilx': 'ilx_0101431',  # brain
        'relationship_ilx': 'ilx_0115023',  # Related to
        'entity2_ilx': 'ilx_0108124',  # organ
    }
    update_entity_data = {
        'ilx_id': 'ilx_0101431',
        'label': 'Brain',
        'definition': 'update_test!!',
        'type': 'fde',
        'comment': 'test comment',
        'superclass': 'ilx_0108124',
        'synonyms': ['test', 'test2', 'test2'],
    }
    # resp = sci.delete_annotation(**{
    #     'term_ilx_id': 'ilx_0101431', # brain ILX ID
    #     'annotation_type_ilx_id': 'ilx_0115071', # hasConstraint ILX ID
    #     'annotation_value': 'test_12345',
    # })
    relationship = {
        # (R)N6 chemical ILX ID
        'entity1_ilx': 'http://uri.interlex.org/base/ilx_0100001',
        # Afferent projection ILX ID
        'relationship_ilx': 'http://uri.interlex.org/base/ilx_0112772',
        # 1,2-Dibromo chemical ILX ID
        'entity2_ilx': 'http://uri.interlex.org/base/ilx_0100000',
    }
    # print(sci.add_relationship(**relationship))
    # print(resp)
    # print(sci.update_entity(**update_entity_data))
    # print(sci.add_raw_entity(entity))
    # print(sci.add_entity(**simple_entity))
    # print(sci.add_annotation(**annotation))
    # print(sci.add_relationship(**relationship))


if __name__ == '__main__':
    examples()
