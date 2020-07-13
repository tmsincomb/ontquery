from copy import deepcopy
import json
import os
import random
import string
import unittest

import pytest

from ontquery.plugins.services.interlex_client import InterLexClient
from ontquery.plugins.services.interlex import InterLexRemote
import ontquery as oq
from .common import skipif_no_net, SKIP_NETWORK, log


API_BASE = 'https://test3.scicrunch.org/api/1/'
TEST_PREFIX = 'tmp'  # sigh
TEST_TERM_ID = f'{TEST_PREFIX}_0738406'
TEST_TERM2_ID = f'{TEST_PREFIX}_0738409'
TEST_SUPERCLASS_ID = f'{TEST_PREFIX}_0738397'
TEST_ANNOTATION_ID = f'{TEST_PREFIX}_0738407'
TEST_RELATIONSHIP_ID = f'{TEST_PREFIX}_0738408'


NO_API_KEY = False
NOAUTH = False
if not SKIP_NETWORK:
    try:
        ilx_cli = InterLexClient(base_url=API_BASE)
        ilxremote = InterLexRemote(apiEndpoint=API_BASE)
        ilxremote.setup(instrumented=oq.OntTerm)
    except InterLexClient.NoApiKeyError as e:
        log.exception(e)
        NO_API_KEY = True
    except InterLexClient.IncorrectAuthError as e:
        NOAUTH = True


skipif_no_auth = pytest.mark.skipif(NOAUTH, reason='no basic auth')
skipif_no_api_key = pytest.mark.skipif(NO_API_KEY, reason='no api key')


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


@skipif_no_net
@skipif_no_auth
@skipif_no_api_key
def test_api_key():
    ilxremote = InterLexRemote(apiEndpoint=API_BASE)
    ilxremote.setup(instrumented=oq.OntTerm)
    ilx_cli = ilxremote.ilx_cli
    os.environ['INTERLEX_API_KEY'] = 'fake_key_12345'  # shadows the scicrunch key in tests
    with pytest.raises(ilx_cli.IncorrectAPIKeyError, match="api_key given is incorrect."):
        ilxremote = InterLexRemote(apiEndpoint=API_BASE)
        ilxremote.setup(instrumented=oq.OntTerm)

    os.environ.pop('INTERLEX_API_KEY')  # unshadow
    assert not os.environ.get('INTERLEX_API_KEY')


@skipif_no_net
@skipif_no_auth
@skipif_no_api_key
@pytest.mark.parametrize("test_input, expected", [
    ("ILX:123", 'ilx_123'),
    ("ilx_123", 'ilx_123'),
    ("TMP:123", f'{TEST_PREFIX}_123'),
    ("tmp_123", f'{TEST_PREFIX}_123'),
    ('http://uri.interlex.org/base/tmp_123', f'{TEST_PREFIX}_123'),
    ('http://fake_url.org/tmp_123', f'{TEST_PREFIX}_123'),
])
def test_fix_ilx(test_input, expected):
    assert ilx_cli.fix_ilx(test_input) == expected


@skipif_no_net
@skipif_no_auth
@skipif_no_api_key
class Test(unittest.TestCase):
    def test_query_elastic(self):
        label = 'brain'
        body = {
            'query': {
                'bool': {
                    'should': [
                        {
                            'fuzzy': {
                                'label': {
                                    'value': label,
                                    'fuzziness': 1
                                    }
                                }
                            },
                        {
                            'match': {
                                'label': {
                                    'query': label,
                                    'boost': 100
                                }
                            }
                        }
                    ]
                }
            }
        }
        params = {
            'term': label,
            'key': ilx_cli.api_key,
            'query': json.dumps(body['query']),
            "size": 1,
            "from": 0
        }
        hits = ilx_cli.query_elastic(**params)
        assert hits[0]['label'].lower() == 'brain'
        hits = ilx_cli.query_elastic(label='brain')
        assert hits[0]['label'].lower() == 'brain'
        hits = ilx_cli.query_elastic(body=body)
        assert hits[0]['label'].lower() == 'brain'

    def test_get_entity(self):
        ilx_id = TEST_SUPERCLASS_ID
        entity = ilx_cli.get_entity(ilx_id)
        assert entity['ilx'] == TEST_SUPERCLASS_ID

    def test_add_annotation(self):
        random_label = 'test_' + id_generator(size=12)
        entity = {
            'label': random_label,
            'type': 'annotation',  # broken at the moment NEEDS PDE HARDCODED
            'definition': 'Part of the central nervous system',
            'comment': 'Cannot live without it',
            'superclass': TEST_SUPERCLASS_ID,  # ILX ID for Organ
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
        added_entity_data = ilx_cli.add_entity(**deepcopy(entity))

        annotation = {
            'term_ilx_id': TEST_TERM_ID,  # brain ILX ID
            'annotation_type_ilx_id': added_entity_data['ilx'],  # hasDbXref ILX ID
            'annotation_value': 'test_annotation_value',
        }

        added_anno_data = ilx_cli.add_annotation(**annotation.copy())
        assert added_anno_data['id'] is not False
        assert added_anno_data['tid'] is not False
        assert added_anno_data['annotation_tid'] is not False
        assert added_anno_data['value'] == annotation['annotation_value']

        # MAKING SURE DUPLICATE STILL RETURNS SAME INFO
        added_anno_data = ilx_cli.add_annotation(**annotation.copy())
        assert added_anno_data['id'] is not False
        assert added_anno_data['tid'] is not False
        assert added_anno_data['annotation_tid'] is not False
        assert added_anno_data['value'] == annotation['annotation_value']

        bad_anno = annotation.copy()
        bad_anno['term_ilx_id'] = 'ilx_rgb'
        with pytest.raises(ilx_cli.EntityDoesNotExistError,
                           match=r"term_ilx_id: ilx_rgb does not exist",):
            ilx_cli.add_annotation(**bad_anno)

        bad_anno = annotation.copy()
        bad_anno['annotation_type_ilx_id'] = 'ilx_rgb'
        with pytest.raises(ilx_cli.EntityDoesNotExistError,
                           match=r"annotation_type_ilx_id: ilx_rgb does not exist",):
            ilx_cli.add_annotation(**bad_anno)

    def test_add_entity(self):
        random_label = 'test_' + id_generator(size=12)

        # TODO: commented out key/vals can be used for services test later
        entity = {
            'label': random_label,
            'type': 'term',
            'definition': 'Part of the central nervous system',
            'comment': 'Cannot live without it',
            # 'subThingOf': 'http://uri.interlex.org/base/ilx_0108124',  # ILX ID for Organ
            'superclass': 'http://uri.interlex.org/base/'+TEST_SUPERCLASS_ID,  # ILX ID for Organ
            'synonyms': ['Encephalon', {'literal': 'Cerebro', 'type': 'exact'}],
            'existing_ids': [
                {
                    'iri': 'http://uri.neuinfo.org/nif/nifstd/birnlex_796',
                    'curie': 'BIRNLEX:796',
                    'preferred': '0',
                },
                {
                    'iri': 'http://uri.neuinfo.org/nif/nifstd/birnlex_797',
                    'curie': 'BIRNLEX:797',
                },
            ]
            # 'predicates': {
            #     'http://uri.interlex.org/base/+TEST_ANNOTATION_ID': 'sample_value',  # hasDbXref beta ID
            # }
        }
        added_entity_data = ilx_cli.add_entity(**deepcopy(entity))

        assert added_entity_data['label'] == entity['label']
        assert added_entity_data['type'] == entity['type']
        assert added_entity_data['definition'] == entity['definition']
        assert added_entity_data['comment'] == entity['comment']
        #assert added_entity_data['superclasses'][0]['ilx'] == entity['subThingOf'].replace('http://uri.interlex.org/base/', '')
        assert added_entity_data['superclass'] == entity['superclass']
        assert added_entity_data['synonyms'][0]['literal'] == entity['synonyms'][0]
        assert added_entity_data['synonyms'][1]['literal'] == entity['synonyms'][1]['literal']

        ### ALREADY EXISTS TEST
        added_entity_data = ilx_cli.add_entity(**deepcopy(entity))

        assert added_entity_data['label'] == entity['label']
        assert added_entity_data['type'] == entity['type']
        assert added_entity_data['definition'] == entity['definition']
        assert added_entity_data['comment'] == entity['comment']
        #assert added_entity_data['superclasses'][0]['ilx'] == entity['subThingOf'].replace('http://uri.interlex.org/base/', '')
        assert added_entity_data['superclass'] == entity['superclass']
        assert added_entity_data['synonyms'][0]['literal'] == entity['synonyms'][0]
        assert added_entity_data['synonyms'][1]['literal'] == entity['synonyms'][1]['literal']

    def test_add_entity_minimum(self):
        random_label = 'test_' + id_generator(size=12)

        # TODO: commented out key/vals can be used for services test later
        entity = {
            'label': random_label,
            'type': 'term',  # broken at the moment NEEDS PDE HARDCODED
        }
        added_entity_data = ilx_cli.add_entity(**entity.copy())

        assert added_entity_data['label'] == entity['label']
        assert added_entity_data['type'] == entity['type']

        ### ALREADY EXISTS TEST
        added_entity_data = ilx_cli.add_entity(**entity.copy())

        assert added_entity_data['label'] == entity['label']
        assert added_entity_data['type'] == entity['type']

    def test_partial_update(self):
        def rando_str():
            return 'test_' + id_generator(size=12)
        entity = {
            'label': rando_str(),
            'type': 'term',
        }
        added_entity_data = ilx_cli.add_entity(**deepcopy(entity))
        partially_updated_entity = ilx_cli.partial_update(
            curie='ILX:'+added_entity_data['ilx'].split('_')[-1],
            definition='new',
            comment='new',
            synonyms=[
                'new1',
                {'literal': 'new2'},
                {'literal': 'new3', 'type': 'obo:hasExactSynonym'}
            ],
            existing_ids=[{
                'iri': 'http://fake.org/123',
                'curie': 'FAKE:123',
                'preferred': '0'
            }],
        )
        assert partially_updated_entity['definition'] == 'new'
        entity = {
            'label': rando_str(),
            'type': 'term',
            'definition': 'original',
            'comment': 'original',
        }
        added_entity_data = ilx_cli.add_entity(**entity.copy())
        partially_updated_entity = ilx_cli.partial_update(
            curie='ILX:'+added_entity_data['ilx'].split('_')[-1],
            definition='new',
            comment='new',
            synonyms=[
                'new1',
                {'literal': 'new2'},
                {'literal': 'new3', 'type': 'obo:hasExactSynonym'}
            ],
            existing_ids=[{
                'iri': 'http://fake.org/123',
                'curie': 'FAKE:123',
                'preferred': '0'
            }],
        )
        assert partially_updated_entity['definition'] == 'original'

    def test_update_entity(self):

        def rando_str():
            return 'test_' + id_generator(size=12)

        entity = {
            'label': rando_str(),
            'type': 'term',  # broken at the moment NEEDS PDE HARDCODED
            'synonyms': 'original_synonym',
        }
        added_entity_data = ilx_cli.add_entity(**entity.copy())

        label = 'troy_test_term'
        type = 'fde'
        superclass = added_entity_data['ilx']
        definition = rando_str()
        comment = rando_str()
        synonym = rando_str()

        update_entity_data = {
            'ilx_id': TEST_TERM_ID,
            'label': label,
            'definition': definition,
            'type': type,
            'comment': comment,
            'superclass': superclass,
            'add_synonyms': ['original_synonym', 'test', synonym],
            # should delete new synonym before it was even added to avoid endless synonyms
            'delete_synonyms': ['original_synonym', {'literal': synonym, 'type': None}],
        }

        updated_entity_data = ilx_cli.update_entity(**update_entity_data.copy())
        assert updated_entity_data['label'] == label
        assert updated_entity_data['definition'] == definition
        assert updated_entity_data['type'] == type
        assert updated_entity_data['comment'] == comment
        assert updated_entity_data['superclass'].rsplit('/', 1)[-1] == superclass.rsplit('/', 1)[-1]
        # test if random synonym was added
        assert synonym not in [d['literal'] for d in updated_entity_data['synonyms']]
        # test if dupclicates weren't created
        assert [d['literal'] for d in updated_entity_data['synonyms']].count('test') == 1

    def test_annotation(self):
        annotation_value = 'test_' + id_generator()
        resp = ilx_cli.add_annotation(**{
            'term_ilx_id': TEST_TERM_ID,  # brain ILX ID
            'annotation_type_ilx_id': TEST_ANNOTATION_ID,  # spont firing ILX ID
            'annotation_value': annotation_value,
        })
        assert resp['value'] == annotation_value
        resp = ilx_cli.delete_annotation(**{
            'term_ilx_id': TEST_TERM_ID,  # brain ILX ID
            'annotation_type_ilx_id': TEST_ANNOTATION_ID,  # spont firing ILX ID
            'annotation_value': annotation_value,
        })
        # If there is a response than it means it worked. If you try this again it will 404 if my net doesnt catch it
        assert resp['id'] is not None
        assert resp['value'] == ' '

    def test_relationship(self):
        random_label = 'my_test' + id_generator()
        entity_resp = ilx_cli.add_entity(**{
            'label': random_label,
            'type': 'term',
        })

        entity1_ilx = entity_resp['ilx']
        relationship_ilx = TEST_RELATIONSHIP_ID # is part of ILX ID
        entity2_ilx = TEST_TERM_ID #1,2-Dibromo chemical ILX ID

        relationship_resp = ilx_cli.add_relationship(**{
            'entity1_ilx': entity1_ilx,
            'relationship_ilx': relationship_ilx,
            'entity2_ilx': entity2_ilx,
        })

        assert relationship_resp['term1_id'] == ilx_cli.get_entity(entity1_ilx)['id']
        assert relationship_resp['relationship_tid'] == ilx_cli.get_entity(relationship_ilx)['id']
        assert relationship_resp['term2_id'] == ilx_cli.get_entity(entity2_ilx)['id']

        relationship_resp = ilx_cli.delete_relationship(**{
            'entity1_ilx': entity_resp['ilx'], # (R)N6 chemical ILX ID
            'relationship_ilx': relationship_ilx,
            'entity2_ilx': entity2_ilx,
        })

        # If there is a response than it means it worked.
        assert relationship_resp['term1_id'] == ' '
        assert relationship_resp['relationship_tid'] == ' '
        assert relationship_resp['term2_id'] == ' '

    # todo discuss if we should have comment, type and superclass for return
    def test_entity_remote(self):
        random_label = 'test_' + id_generator(size=12)

        # TODO: commented out key/vals can be used for services test later
        entity = {
            'label': random_label,
            'type': 'term',  # broken at the moment NEEDS PDE HARDCODED
            'definition': 'Part of the central nervous system',
            'comment': 'Cannot live without it',
            # 'subThingOf': 'http://uri.interlex.org/base/ilx_0108124',  # ILX ID for Organ
            'subThingOf': 'http://uri.interlex.org/base/'+TEST_TERM_ID,  # ILX ID for Organ
            'synonyms': ['Encephalon', 'Cerebro'],
            'predicates': {
                'http://uri.interlex.org/base/'+TEST_ANNOTATION_ID: 'sample_value',  # spont firing beta ID | annotation
                'http://uri.interlex.org/base/'+TEST_RELATIONSHIP_ID: 'http://uri.interlex.org/base/'+TEST_TERM_ID,  # relationship
            }
        }
        ilxremote_resp = ilxremote.add_entity(**entity)
        added_entity_data = ilx_cli.get_entity(ilxremote_resp['curie'])
        added_annotation = ilx_cli.get_annotation_via_tid(added_entity_data['id'])[0]
        added_relationship = ilx_cli.get_relationship_via_tid(added_entity_data['id'])[0]

        assert ilxremote_resp['label'] == entity['label']
        # assert ilxremote_resp['type'] == entity['type']
        assert ilxremote_resp['definition'] == entity['definition']
        # assert ilxremote_resp['comment'] == entity['comment']
        # assert ilxremote_resp['superclass'] == entity['superclass']
        assert ilxremote_resp['synonyms'][0]['literal'] == entity['synonyms'][0]
        assert ilxremote_resp['synonyms'][1]['literal'] == entity['synonyms'][1]

        assert added_annotation['value'] == 'sample_value'
        assert added_annotation['annotation_term_ilx'] == TEST_ANNOTATION_ID
        assert added_relationship['relationship_term_ilx'] == TEST_RELATIONSHIP_ID
        assert added_relationship['term2_ilx'] == TEST_TERM_ID
        entity = {
            'ilx_id': ilxremote_resp['curie'],
            'label': random_label + '_update',
            # 'type': 'term', # broken at the moment NEEDS PDE HARDCODED
            'definition': 'Updated definition!',
            'comment': 'Cannot live without it UPDATE',
            'subThingOf': 'http://uri.interlex.org/base/'+TEST_TERM_ID,  # ILX ID for Organ
            'add_synonyms': ['Encephalon', 'Cerebro_update'],
            'predicates_to_add': {
                # DUPCLICATE CHECK
                'http://uri.interlex.org/base/'+TEST_ANNOTATION_ID: 'sample_value',  # spont firing beta ID | annotation
                'http://uri.interlex.org/base/'+TEST_ANNOTATION_ID: 'sample_value2',  # spont firing beta ID | annotation
                'http://uri.interlex.org/base/'+TEST_RELATIONSHIP_ID: 'http://uri.interlex.org/base/'+TEST_TERM2_ID  # relationship
            },
            'predicates_to_delete': {
                # DELETE ORIGINAL
                'http://uri.interlex.org/base/'+TEST_ANNOTATION_ID: 'sample_value',  # spont firing beta ID | annotation
                'http://uri.interlex.org/base/'+TEST_RELATIONSHIP_ID: 'http://uri.interlex.org/base/'+TEST_TERM2_ID,  # relationship
            }
        }
        ilxremote_resp = ilxremote.update_entity(**deepcopy(entity))
        added_entity_data = ilx_cli.get_entity(ilxremote_resp['curie'])
        added_annotations = ilx_cli.get_annotation_via_tid(added_entity_data['id'])
        added_relationships = ilx_cli.get_relationship_via_tid(added_entity_data['id'])
        assert ilxremote_resp['label'] == entity['label']
        # assert ilxremote_resp['type'] == entity['type']
        assert ilxremote_resp['definition'] == entity['definition']
        # assert ilxremote_resp['comment'] == entity['comment']
        # assert ilxremote_resp['superclass'] == entity['superclass']
        assert ilxremote_resp['synonyms'][0] == entity['add_synonyms'][0]
        assert ilxremote_resp['synonyms'][2] == entity['add_synonyms'][1]

        assert len(added_annotations) == 1
        assert len(added_relationships) == 1
        assert added_annotations[0]['annotation_term_ilx'] == TEST_ANNOTATION_ID
        assert added_annotations[0]['value'] == 'sample_value2'
        # would check term1_ilx, but whoever made it forgot to make it a key...
        assert added_relationships[0]['relationship_term_ilx'] == TEST_RELATIONSHIP_ID
        assert added_relationships[0]['term2_ilx'] == TEST_TERM_ID

    def test_merge_records(self):
        complex_syn = [{'literal': 'alt label', 'type': ''}]
        complex_syn_wt = [{'literal': 'alt label', 'type': 'exact'}]
        complex_syn_wt2 = [{'literal': 'alt label 2', 'type': 'exact'}]
        # NULL CHECK #
        complete_empty_check = ilx_cli._merge_records(
            ref_records=[],
            records=[],
            on=['literal'],
            alt=['type'],
        )
        empty_check = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn),
            records=[],
            on=['literal'],
            alt=['type'],
        )
        empty_check_rev = ilx_cli._merge_records(
            ref_records=[],
            records=deepcopy(complex_syn),
            on=['literal'],
            alt=['type'],
        )
        assert complete_empty_check == []
        assert empty_check == complex_syn
        assert empty_check_rev == complex_syn
        # ON CHECK #
        on_check_neutral = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn),
            records=deepcopy(complex_syn_wt),
            on=['literal'],
        )
        on_check_neutral2 = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn_wt),
            records=deepcopy(complex_syn),
            on=['literal'],
        )
        on_check_add = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn),
            records=deepcopy(complex_syn_wt2),
            on=['literal'],
        )
        assert on_check_neutral == complex_syn
        assert on_check_neutral2 == complex_syn_wt
        assert on_check_add == complex_syn + complex_syn_wt2
        # ALT CHECK #
        alt_check = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn_wt),
            records=deepcopy(complex_syn),
            on=['literal'],
            alt=['type'],
        )
        alt_check_update = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn),
            records=deepcopy(complex_syn_wt),
            on=['literal'],
            alt=['type'],
        )
        assert alt_check == complex_syn_wt
        assert alt_check_update == complex_syn_wt
        # PASSIVE CHECK #
        passive_check = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn_wt),
            records=deepcopy(complex_syn),
            on=['literal'],
            alt=['type'],
            passive=True
        )
        passive_check_add = ilx_cli._merge_records(
            ref_records=deepcopy(complex_syn),
            records=deepcopy(complex_syn_wt),
            on=['literal'],
            alt=['type'],
            passive=True
        )
        assert passive_check == complex_syn_wt
        assert passive_check_add == complex_syn + complex_syn_wt

    def test_remove_records(self):
        complex_syn = [{'literal': 'alt label', 'type': ''}]
        complex_syn_wt = [{'literal': 'alt label', 'type': 'exact'}]
        complex_syn_wt2 = [{'literal': 'alt label 2', 'type': 'exact'}]
        empty = ilx_cli._remove_records(
            ref_records=[],
            records=[],
            on=['literal', 'type'],
        )
        neutral = ilx_cli._remove_records(
            ref_records=deepcopy(complex_syn_wt),
            records=deepcopy(complex_syn),
            on=['literal', 'type'],
        )
        neutral_alt = ilx_cli._remove_records(
            ref_records=deepcopy(complex_syn_wt),
            records=deepcopy(complex_syn_wt2),
            on=['literal', 'type'],
        )
        removed = ilx_cli._remove_records(
            ref_records=deepcopy(complex_syn_wt),
            records=deepcopy(complex_syn_wt),
            on=['literal', 'type'],
        )
        assert empty == []
        assert neutral == complex_syn_wt
        assert neutral_alt == complex_syn_wt
        assert removed == []