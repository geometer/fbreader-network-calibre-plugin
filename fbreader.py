__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.web_store_dialog import WebStoreDialog

from PyQt5.Qt import (
	QObject, QSettings, QByteArray, QNetworkCookie, QNetworkCookieJar)

from calibre.web.jsbrowser.browser import Browser

class MyNetworkCookieJar(QNetworkCookieJar):
	def __init__(self, parent=None):
		QNetworkCookieJar.__init__(self, parent)
		self.storage = QSettings(QSettings.IniFormat, QSettings.UserScope, "fbreader", "plugin")
		self.loadCookies()

	def setCookiesFromUrl(self, cookieList, url):
		res = QNetworkCookieJar.setCookiesFromUrl(self, cookieList, url)
		self.saveCookies()
		return res

	def saveCookies(self):
		cookies = QByteArray()
		for cookie in self.allCookies():
			if not cookie.isSessionCookie():
				cookies.append(cookie.toRawForm())
				cookies.append("\n")
		self.storage.setValue("cookies", cookies)

	def loadCookies(self):
		tmp = self.storage.value("cookies")
		if not tmp:
			return
#		cookies = tmp.toByteArray()
		cookieList = QNetworkCookie.parseCookies(tmp)
		self.setAllCookies(cookieList)


class FBReaderNetworkStore(BasicStoreConfig, OpenSearchOPDSStore):
	web_url = 'https://books.fbreader.org/catalog'
	open_search_url = 'https://books.fbreader.org/static/opensearch.xml'

	def open(self, parent=None, detail_item=None, external=False):
		if not hasattr(self, 'web_url'):
			return

		if external or self.config.get('open_external', False):
			open_url(QUrl(detail_item if detail_item else self.web_url))
		else:
			d = WebStoreDialog(self.gui, self.web_url, parent, detail_item, create_browser=self.create_browser)
			d.setWindowTitle(self.name)
			d.set_tags(self.config.get('tags', ''))
			d.view.cookie_jar = MyNetworkCookieJar()
			d.view.page().networkAccessManager().setCookieJar(d.view.cookie_jar)
			d.exec_()
