__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore

class FBReaderNetworkStore(BasicStoreConfig, OpenSearchOPDSStore):
    web_url = 'https://books.fbreader.org/catalog'
    open_search_url = 'https://books.fbreader.org/static/opensearch.xml'
