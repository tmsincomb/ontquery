# TEST InterLex endpoints
import ontquery as oq


def interlex_client(host: str = 'test3.scicrunch.org', scheme: str = 'https') -> object:
    """ Direct InterLex API wrapper setup.

        Does not use other utilities of this library to avoid crashing if
        the goal is to interact with only InterLex.

    :param host: host of URL
    :param scheme: Scheme of URL
    :return: InterlexClient
    """
    InterLexRemote = oq.plugin.get('InterLex')
    api = f'{scheme}://{host}/api/1'
    ilx_cli = InterLexRemote(apiEndpoint=api)
    ilx_cli.setup(instrumented=oq.OntTerm)
    ilx_cli.OntTerm.query_init(ilx_cli)
    return ilx_cli
