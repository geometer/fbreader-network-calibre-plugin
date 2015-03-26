# -*- coding: utf-8 -*-

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from calibre.customize import InterfaceActionBase

class ActionUploadToFBReader(InterfaceActionBase):
    name = 'Upload to FBReader'
    actual_plugin = 'calibre_plugins.upload_fbreader.fbreader:FBReaderUploadAction'
    description = _('Upload to books.fbreader.org')
