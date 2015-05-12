# -*- coding: utf-8 -*-

__license__ = 'MIT'
__copyright__ = '2015, FBReader.ORG Limited <support@fbreader.org>'

from calibre.customize import InterfaceActionBase

class ActionFBReaderSync(InterfaceActionBase):
    name = 'FBReader Sync'
    actual_plugin = 'calibre_plugins.fbreader_sync.fbreader:FBReaderSyncAction'
    description = _('Synchronise library with FBReader® Book Network')
    author = 'FBReader.ORG Limited'
