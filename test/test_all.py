import os
import unittest
import ontquery
from pyontutils import core, config
from IPython import embed

class OntTerm(ontquery.OntTerm):
    """ Test subclassing """

class TestAll(unittest.TestCase):
    def setUp(self):
        ontquery.OntCuries(core.PREFIXES)
        #self.query = OntQuery(localonts, remoteonts1, remoteonts2)  # provide by default maybe as ontquery?
        #bs = ontquery.BasicService()  # TODO
        #self.query = ontquery.OntQuery(bs, upstream=OntTerm)
        ontquery.QueryResult._OntTerm = OntTerm
        if 'SCICRUNCH_API_KEY' in os.environ:
            services = ontquery.SciCrunchRemote(api_key=config.get_api_key()),
        else:
            services = ontquery.SciCrunchRemote(apiEndpoint='http://localhost:9000/scigraph'),

        self.query = ontquery.OntQueryCli(*services)
        ontquery.OntTerm.query = ontquery.OntQuery(*services)
        #self.APIquery = OntQuery(SciGraphRemote(api_key=get_api_key()))

    def test_query(self):

        self.query('brain')
        self.query(term='brain')
        #self.query(prefix='UBERON', suffix='0000955')  # only for OntId
        self.query(search='thalamus')  # will probably fail with many results to choose from
        self.query(prefix='MBA', abbrev='TH')

        uberon = ontquery.OntQueryCli(*self.query, prefix='UBERON')
        brain_result = uberon('brain')  # -> OntTerm('UBERON:0000955', label='brain')

        species = ontquery.OntQuery(*self.query, category='species')
        mouse_result = species('mouse')  # -> OntTerm('NCBITaxon:10090', label='mouse')

        list(self.query.predicates)

    def test_term(self):
        brain = OntTerm('UBERON:0000955')
        brain = OntTerm(curie='UBERON:0000955')
        OntTerm('UBERON:0000955', label='brain')
        try:
            OntTerm('UBERON:0000955', label='not actually the brain')
            assert False, 'should not get here'
        except ValueError:
            assert True, 'expect to fail'

        try:
            OntTerm('UBERON:0000955', label='not actually the brain', validated=False)
            assert False, 'should not get here'
        except ValueError:
            assert True, 'expect to fail'

    def test_term_query(self):
        _query = ontquery.OntTerm.query
        ontquery.OntTerm.query = self.query
        try:
            OntTerm(label='brain')
            assert False, 'should not get here!'
        except TypeError:
            assert True, 'fails as expected'

        ontquery.OntTerm.query = _query

        try:
            OntTerm(label='brain')
            assert False, 'should not get here!'
        except ValueError:
            assert True, 'fails as expected'

        try:
            OntTerm(label='dorsal plus ventral thalamus')
            assert False, 'should not get here!'
        except ValueError:
            assert True, 'fails as expected'


    def test_id(self):
        ontquery.OntId('UBERON:0000955')
        ontquery.OntId('http://purl.obolibrary.org/obo/UBERON_0000955')
        ontquery.OntId(prefix='UBERON', suffix='0000955')

    def test_predicates(self):
        self.query.raw = True
        pqr = self.query(iri='UBERON:0000955', predicates=('hasPart:',))
        self.query.raw = False
        pt = pqr.OntTerm
        preds = OntTerm('UBERON:0000955')('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')
        preds1 = pt('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')

    def test_curies(self):
        ontquery.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/'
        ontquery.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/'
        try:
            ontquery.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/fail/'
            assert False, 'should not get here!'
        except KeyError:
            assert True, 'should fail'

        ontquery.OntId('new-prefix:working')
        
