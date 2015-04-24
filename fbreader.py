# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

import platform

from contextlib import closing


from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.actions import InterfaceAction

from PyQt5.Qt import *
from cookielib import CookieJar, Cookie

import hashlib
import json
import urllib2
import os
import threading

from .status_dialog import StatusDialog, Status

BLOCKSIZE = 65536
DOMAIN = "books.fbreader.org"
BASE_URL = "https://books.fbreader.org/"

class FBReaderUploadAction(InterfaceAction):

	name = 'Upload to FBReader'
	action_spec = ('Upload to FBReader', None, None, None)
	action_type = 'current'

	def genesis(self):
		pixmap = QPixmap()
		pixmap.loadFromData(self.load_resources(['fbreader.png']).itervalues().next())
		icon = QIcon(pixmap)
		self.qaction.setIcon(icon)
		self.qaction.triggered.connect(self.upload)
		self.controller = UploadController(self.gui)

	def upload(self):
		rows = self.gui.library_view.selectionModel().selectedRows()
		if not rows or len(rows) == 0:
			return error_dialog(self.gui, 'No books selected',
								'You must select one or more books to perform this action.', show=True)
		login = self.check_login()
		if login == 1:#not authorized
			msgBox = QMessageBox()
			msgBox.setWindowTitle("Not authorized")
			msgBox.setText("Would you kindly login into books.fbreader.org?")
			msgBox.exec_()
			self.open()
			if self.check_login() != 0:
				return error_dialog(self.gui, 'You still not authorized!',
									'Shame on you!', show=True)
		elif login != 0:
			return error_dialog(self.gui, 'Error',
									'Something awful happened!', show=True)
		book_ids = self.gui.library_view.get_selected_ids()
		db = self.gui.library_view.model().db

		paths = []

		for book_id in book_ids:
			mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
			title, formats = mi.title, mi.formats
			for f in formats:
				path = db.format_abspath(book_id, f, index_is_id=True)
				name = title
				paths.append((path, name, f))
		StatusDialog(self.controller, paths, self.gui).exec_()

	def open(self):
		from calibre.gui2.store.web_store_dialog import WebStoreDialog
		d = WebStoreDialog(self.gui, "https://books.fbreader.org/catalog", None, None, create_browser=self.create_browser)
		d.setWindowTitle("FBReader® Book Network")
		d.view.cookie_jar = MyNetworkCookieJar(True)
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
		qjar = MyNetworkCookieJar(False)
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
		except:
			return 2
		return 2  # What can we do here???


class UploadController(QObject):


#	updated = pyqtSignal()

	def __init__(self, parent=None):
		QObject.__init__(self, parent)
		self.pool = QThreadPool(self)
		self.pool.setMaxThreadCount(10)
		self.uploaders = {}

	def get_uploader(self, p):
		if p not in self.uploaders.keys():
				upl = Uploader(p, self)
#				upl.updated.connect(self.onUpdated)
				self.uploaders[p] = upl
		return self.uploaders[p]



	def forcecheck(self, path):
		self.get_uploader(path).forcecheck()

	def check(self, path):
		self.get_uploader(path).check()

	def upload(self, path):
		self.get_uploader(path).upload()

#	def onUpdated(self):
#		self.updated.emit()


import resource
import fcntl
import os

def get_open_fds():
    fds = []
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    for fd in range(0, soft):
        try:
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        except IOError:
            continue
        fds.append(fd)
    return fds

class My_Runnable(QRunnable):
	def __init__(self, func):
		QRunnable.__init__(self)
		self.func = func

	def run(self):
		apply(self.func)


class Uploader(QObject):

	updated = pyqtSignal()
	hashed = pyqtSignal()

	def __init__(self, path, parent=None):
		QObject.__init__(self, parent)
		self.url = BASE_URL + "app/book.upload"
		self.path = path
		self.manager = QNetworkAccessManager(self)
		self.manager.setCookieJar(MyNetworkCookieJar(False, self))
		self.status = Status()
		self.progress = 0
		self.lock = threading.RLock() #FIXME I hope it works with qt threads
		self.need_upload = False
		self.hash = None
		self.hashed.connect(self.__check__)


	def forcecheck(self):
		with self.lock:
			if self.status.inprocess:
				return
			self.status = Status()
			self.check()

	def check(self):
		with self.lock:
			if self.status.inprocess:
				return
			if self.status.exists.known():
				return
			self.status.inprocess = True
			r = My_Runnable(lambda: self.__hash__())
			self.parent().pool.start(r)


	def upload(self):
		with self.lock:
			if self.status.inprocess:
				self.need_upload = True
				self.updated.emit()
				return
			if not self.status.exists.known():
				self.status.inprocess = True
				self.need_upload = True
				r = My_Runnable(lambda: self.__check__(self.onCheck))
				self.parent().pool.start(r)
			elif not self.status.exists.value():
				self.status.inprocess = True
				self.__upload__()
			self.updated.emit()

	def onCheck(self):
		self.onCheckAndMaybeUpload(self.need_upload, self.sender())

#	def onCheckAndUpload(self):
#		self.onCheckAndMaybeUpload(True, self.sender())

	def onCheckAndMaybeUpload(self, upload, sender):
		with self.lock:
			self.__onCheck__(sender)
			if upload and (not self.status.error) and (not self.status.exists.value):
				self.status.inprocess = True
				self.__upload__()
			else:
				self.status.inprocess = False
			self.updated.emit()

	def onUpload(self):
		with self.lock:
			self.need_upload = False
			self.status.inprocess = False
			self.__onUpload__(self.sender())
			self.updated.emit()

	def __onUpload__(self, sender):
		if sender.error() != 0:
			self.status.error = True
			return
		try:
			data = self.sender().readAll()
			res = json.loads(str(data))
			if 'error' in res[0]['result'].keys():
				self.status.error = True
				self.status.error_message = res[0]['result']['error']
				return
			self.status.uploaded.set_value(True)
			self.status.exists.set_value(True)
		except Exception as e:
			self.status.error = True
			return

	def __check__(self):
		self.referer = BASE_URL + "app/book.status.by.hash?sha1=" + self.hash
		self.request = QNetworkRequest(QUrl(self.referer))
		self.reply = self.manager.get(self.request)
		self.reply.finished.connect(self.onCheck)

	def __hash__(self):
		hasher = hashlib.sha1()
		print(len(get_open_fds()))
		with open(self.path, 'rb') as afile:
			buf = afile.read(BLOCKSIZE)
			while len(buf) > 0:
				hasher.update(buf)
				buf = afile.read(BLOCKSIZE)
		self.hash = hasher.hexdigest()
		self.hashed.emit()

	def __onCheck__(self, sender):
		if sender.error() != 0:
			self.status.error = True
			return
		try:
			res = json.loads(str(sender.readAll()))
			if res["status"] == "found":
				self.status.exists.set_value(True)
				return
		except Exception as e:
			self.status.error = True
			return
		self.csrftoken = None
		for c in self.manager.cookieJar().allCookies():
			if str(c.domain()) == DOMAIN and str(c.name()) == "csrftoken":
				self.csrftoken = str(c.value())
		if not self.csrftoken:
			self.status.error = True
			return
		self.status.exists.set_value(False)

	def __upload__(self):
		self.multiPart = QHttpMultiPart(QHttpMultiPart.FormDataType, self)
		self.filePart = QHttpPart()
		self.filePart.setHeader(QNetworkRequest.ContentDispositionHeader, QVariant("form-data; name=\"file\"; filename=\"" + os.path.basename(self.path) + "\""));
		self.qfile = QFile(self.path, self)
		self.qfile.open(QIODevice.ReadOnly)
		self.filePart.setBodyDevice(self.qfile)
		self.multiPart.append(self.filePart)
		self.request = QNetworkRequest(QUrl(self.url))
		self.request.setRawHeader("X-CSRFToken", self.csrftoken)
		self.request.setRawHeader("Referer", self.referer)
		self.reply = self.manager.post(self.request, self.multiPart)
		self.reply.finished.connect(self.onUpload)
		self.reply.uploadProgress.connect(self.onProgress)

	def onProgress(self, s, t):
		if (t != 0):
			self.progress = int(100. * s / t)
			self.updated.emit()


#================= from another plugin

class MyNetworkCookieJar(QNetworkCookieJar):
	def __init__(self, writable, parent=None):
		QNetworkCookieJar.__init__(self, parent)
		self.readonly = not writable
		self.storage = QSettings(QSettings.IniFormat, QSettings.UserScope, "fbreader", "plugin")
		self.loadCookies()

	def setCookiesFromUrl(self, cookieList, url):
		res = QNetworkCookieJar.setCookiesFromUrl(self, cookieList, url)
		self.saveCookies()
		return res

	def saveCookies(self):
		if self.readonly:
			return
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





