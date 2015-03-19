# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

import platform

from PyQt5.Qt import (
	QObject, QSettings, QByteArray, QNetworkCookie, QNetworkCookieJar, QUrl)

from contextlib import closing

from cookielib import Cookie

from lxml import etree

from calibre import (browser, guess_extension)
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.utils.opensearch.description import Description
from calibre.utils.opensearch.query import Query
from calibre.web.jsbrowser.browser import Browser
from calibre.utils.magick.draw import thumbnail



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
		cookieList = QNetworkCookie.parseCookies(tmp)
		self.setAllCookies(cookieList)

	def py_cookies_internal(self):
		for c in self.allCookies():
			name, value = map(bytes, (c.name(), c.value()))
			domain = bytes(c.domain())
			initial_dot = domain_specified = domain.startswith(b'.')
			secure = bool(c.isSecure())
			path = unicode(c.path()).strip().encode('utf-8')
			expires = c.expirationDate()
			is_session_cookie = False
			if expires.isValid():
				expires = expires.toTime_t()
			else:
				expires = None
				is_session_cookie = True
			path_specified = True
			if not path:
				path = b'/'
				path_specified = False
			c = Cookie(0,  # version
					name, value,
					None,  # port
					False,  # port specified
					domain, domain_specified, initial_dot, path,
					path_specified,
					secure, expires, is_session_cookie,
					None,  # Comment
					None,  # Comment URL
					{}  # rest
			)
			yield c
	@property
	def py_cookies(self):
		'''
		Return all the cookies set currently as :class:`Cookie` objects.
		Returns expired cookies as well.
		'''
		return list(self.py_cookies_internal())


class FBReaderNetworkStore(BasicStoreConfig, OpenSearchOPDSStore):
	plugin_version = "1.0"
	web_url = 'https://books.fbreader.org/catalog'
#	open_search_url = 'https://books.fbreader.org/static/opensearch.xml'
	base_url = "https://books.fbreader.org"

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


	def create_browser_with_cookies(self):
		user_agent = "FBReader Calibre Plugin/" + FBReaderNetworkStore.plugin_version + " " + platform.system()
		br = browser(user_agent=user_agent)
		for cookie in MyNetworkCookieJar().py_cookies:
			br.cookiejar.set_cookie(cookie)
		return br


	def search(self, query, max_results=10, timeout=60):
		url = "https://books.fbreader.org/opds/search/" + query
		counter = max_results
		br = self.create_browser_with_cookies()
		with closing(br.open(url, timeout=timeout)) as f:
			s = f.read()
			doc = etree.fromstring(s)
			for data in doc.xpath('//*[local-name() = "entry"]'):
				if counter <= 0:
					break

				counter -= 1

				s = SearchResult()

				s.detail_item = ''.join(data.xpath('./*[local-name() = "id"]/text()')).strip()

				for link in data.xpath('./*[local-name() = "link"]'):
					rel = link.get('rel')
					href = link.get('href')
					type = link.get('type')

					if rel and href and type:
						if 'http://opds-spec.org/thumbnail' in rel:
							s.cover_url = href
						elif 'http://opds-spec.org/image/thumbnail' in rel:
							s.cover_url = href
						elif 'http://opds-spec.org/acquisition/buy' in rel:
							s.detail_item = href
						elif 'http://opds-spec.org/acquisition' in rel:
							if type:
								ext = guess_extension(type)
								if type == 'application/fb2+xml':
									ext = '.fb2'
								if ext:
									ext = ext[1:].upper().strip()
									if href[0] == "/":
										href = self.base_url + href
									s.downloads[ext] = href
				s.formats = ', '.join(s.downloads.keys()).strip()

				s.title = ' '.join(data.xpath('./*[local-name() = "title"]//text()')).strip()
				s.author = ', '.join(data.xpath('./*[local-name() = "author"]//*[local-name() = "name"]//text()')).strip()

				price_e = data.xpath('.//*[local-name() = "price"][1]')
				if price_e:
					price_e = price_e[0]
					currency_code = price_e.get('currencycode', '')
					price = ''.join(price_e.xpath('.//text()')).strip()
					s.price = currency_code + ' ' + price
					s.price = s.price.strip()
				if s.cover_url:
					s.cover_bak = s.cover_url
					s.cover_url = None
				yield s

	def get_details(self, search_result, timeout):
		if search_result.cover_bak:
				if search_result.cover_bak[0] == "/":
					search_result.cover_bak = self.base_url + search_result.cover_bak
				br1 = self.create_browser_with_cookies()
				with closing(br1.open(search_result.cover_bak, timeout=timeout)) as f:
					search_result.cover_data = f.read()
				search_result.cover_data = thumbnail(search_result.cover_data, 64, 64)[2]








