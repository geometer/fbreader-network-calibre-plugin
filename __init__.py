# -*- coding: utf-8 -*-

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from calibre.customize import StoreBase

class FBReaderNetworkStore(StoreBase):
    name = 'FBReader® Book Network'
    description = 'Cloud eBook Storage'
    actual_plugin = 'calibre_plugins.store_fbreader.fbreader:FBReaderNetworkStore'
