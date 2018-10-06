import unittest
import rdflib
import ontquery as oq

oq.OntCuries({'rdf': str(rdflib.RDF),
              'rdfs': str(rdflib.RDFS),
              'owl': str(rdflib.OWL),
              'UBERON': 'http://purl.obolibrary.org/obo/UBERON_'})
OntId = oq.OntId

class ServiceBase:
    def setUp(self):
        _query = oq.OntQuery(self.remote)
        class OntTerm(oq.OntTerm):
            query = _query

        self.OntTerm = OntTerm

    def test_ontid(self):
        t = self.OntTerm(OntId('UBERON:0000955'))

    def test_curie(self):
        t = self.OntTerm(curie='UBERON:0000955')

    def test_iri(self):
        t = self.OntTerm(iri='http://purl.obolibrary.org/obo/UBERON_0000955')

    def test_uriref(self):
        t = self.OntTerm(iri=rdflib.URIRef('http://purl.obolibrary.org/obo/UBERON_0000955'))


class TestIlx(ServiceBase, unittest.TestCase):
    remote = oq.InterLexRemote()


class TestSciGraph(ServiceBase, unittest.TestCase):
    remote = oq.SciGraphRemote()


class TestRdflib(ServiceBase, unittest.TestCase):
    g = rdflib.Graph()
    triples = (('UBERON:0000955', 'rdf:type', 'owl:Class'),
               ('UBERON:0000955', 'rdfs:label', 'brain'),)
    for proto_t in triples:
        g.add(rdflib.URIRef(OntId(e)) if ':' in e else rdflib.Literal(e) for e in proto_t)

    remote = oq.rdflibLocal(g)
