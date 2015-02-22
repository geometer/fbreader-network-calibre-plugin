# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.web_store_dialog import WebStoreDialog

from calibre import (browser, guess_extension)
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.utils.opensearch.description import Description
from calibre.utils.opensearch.query import Query

from contextlib import closing

from lxml import etree

from calibre.web.jsbrowser.browser import Browser
from calibre.ptempfile import PersistentTemporaryFile

from mechanize import MozillaCookieJar

from PyQt5.Qt import (
	QObject, QSettings, QByteArray, QNetworkCookie, QNetworkCookieJar, QUrl)


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

	def save_cookies_in_cf(self, cf):
		'''
		Writes QNetworkCookies to Mozilla cookie .txt file.
		'''

		cf.write('# Netscape HTTP Cookie File\n\n')
		for c in self.allCookies():
			cookie = []
			domain = unicode(c.domain())

			cookie.append(domain)
			cookie.append('TRUE' if domain.startswith('.') else 'FALSE')
			cookie.append(unicode(c.path()))
			cookie.append('TRUE' if c.isSecure() else 'FALSE')
			cookie.append(unicode(c.expirationDate().toTime_t()))
			cookie.append(unicode(c.name()))
			cookie.append(unicode(c.value()))

			cf.write('\t'.join(cookie))
			cf.write('\n')

		cf.close()


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


	def create_browser_1(self):
		br = browser()
		cf = PersistentTemporaryFile(suffix='.txt')
		MyNetworkCookieJar().save_cookies_in_cf(cf)
		cj = MozillaCookieJar()
		cj.load(cf.name)
		br.set_cookiejar(cj)
		return br


	def search(self, query, max_results=10, timeout=60):
		if not hasattr(self, 'open_search_url'):
			return

		description = Description(self.open_search_url)
		url_template = description.get_best_template()
		if not url_template:
			return
		oquery = Query(url_template)

		# set up initial values
		oquery.searchTerms = query
		oquery.count = max_results
		url = oquery.url()

		counter = max_results
		br = self.create_browser_1()
		with closing(br.open(url, timeout=timeout)) as f:
			doc = etree.fromstring(f.read())
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
								if ext:
									ext = ext[1:].upper().strip()
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

				yield s













