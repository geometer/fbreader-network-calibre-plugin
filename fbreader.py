# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

import platform

from contextlib import closing


from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.actions import InterfaceAction

import hashlib
import json
import urllib2
import os

BLOCKSIZE = 65536
DOMAIN = "books.fbreader.org"
BASE_URL = "https://books.fbreader.org/"

class FBReaderUploadAction(InterfaceAction):

	name = 'Upload to FBReader'
	action_spec = ('Upload to FBReader', None, None, None)
	action_type = 'current'

	def genesis(self):
		self.qaction.triggered.connect(self.upload)

	def upload(self):
		if self.check_login() == 1:#not authorized
			self.open()
		if self.check_login() != 0:
			return;
		rows = self.gui.library_view.selectionModel().selectedRows()
		if not rows or len(rows) == 0:
			return error_dialog(self.gui, 'No books selected',
								'You must select one or more books to perform this action.', show=True)
		book_ids = self.gui.library_view.get_selected_ids()
		db = self.gui.library_view.model().db

		for book_id in book_ids:
			mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
			title, formats = mi.title, mi.formats
			for f in formats:
				path = db.format_abspath(book_id, f, index_is_id=True)
				self.uploadfile(path)
				
	def open(self):
		from calibre.gui2.store.web_store_dialog import WebStoreDialog
		d = WebStoreDialog(self.gui, "https://books.fbreader.org/catalog", None, None, create_browser=self.create_browser)
		d.setWindowTitle("FBReader® Book Network")
		d.view.cookie_jar = MyNetworkCookieJar()
		d.view.page().networkAccessManager().setCookieJar(d.view.cookie_jar)
		d.exec_()


	def create_browser(self):
		from calibre import browser
		br = browser()
		for cookie in MyNetworkCookieJar().py_cookies:
			br.cookiejar.set_cookie(cookie)
		return br
				
	def check_login(self):
		req = urllib2.Request("https://books.fbreader.org/opds")
		qjar = MyNetworkCookieJar()
		jar = CookieJar()
		for cookie in qjar.py_cookies:
			jar.set_cookie(cookie)
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))
		req.add_header('X-Accept-Auto-Login', "True")
		try:
			response = opener.open(req)
			return 0
		except urllib2.HTTPError as e:
			if e.code == 401:
				return 1
		return 2  # What can we do here???
				
	def uploadfile(self, path):
		hasher = hashlib.sha1()
		with open(path, 'rb') as afile:
			buf = afile.read(BLOCKSIZE)
			while len(buf) > 0:
				hasher.update(buf)
				buf = afile.read(BLOCKSIZE)
		h = hasher.hexdigest()
		url = BASE_URL + "app/book.status.by.hash?sha1=" + h #FIXME: how to send post + cookies?
		req = urllib2.Request(url)
		qjar = MyNetworkCookieJar()
		jar = CookieJar()
		for cookie in qjar.py_cookies:
			jar.set_cookie(cookie)
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))
		response = opener.open(req)
		res = json.loads(response.read())
		if res["status"] != "not found":
			return
		csrftoken = None
		for c in jar:
			if c.domain == DOMAIN and c.name == "csrftoken":
				csrftoken = c.value
		if not csrftoken:
			return

		#UPLOAD
		url = BASE_URL + "app/book.upload"
		#...




#================= from another plugin
from PyQt5.Qt import (
	QObject, QSettings, QByteArray, QNetworkCookie, QNetworkCookieJar, QUrl)
from cookielib import CookieJar, Cookie

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





