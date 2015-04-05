# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

import platform

from contextlib import closing


from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.actions import InterfaceAction

from PyQt5.Qt import (
	QObject, QSettings, QByteArray, QNetworkCookie, QNetworkCookieJar, QUrl, QNetworkRequest, QNetworkAccessManager, QHttpMultiPart, QHttpPart, QFile, QIODevice, QVariant, pyqtSignal, QDialog, QMessageBox, QVBoxLayout, QTableWidget, QTableWidgetItem, QSizePolicy, QHeaderView, QDialogButtonBox, Qt, QColor)
from cookielib import CookieJar, Cookie

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
		rows = self.gui.library_view.selectionModel().selectedRows()
		if not rows or len(rows) == 0:
			return error_dialog(self.gui, 'No books selected',
								'You must select one or more books to perform this action.', show=True)
		if self.check_login() == 1:#not authorized
			msgBox = QMessageBox()
			msgBox.setWindowTitle("Not authorized")
			msgBox.setText("Would you kindly login into books.fbreader.org?")
			msgBox.exec_()
			self.open()
		if self.check_login() != 0:
			return error_dialog(self.gui, 'You still not authorized!',
								'Shame on you!', show=True)
		book_ids = self.gui.library_view.get_selected_ids()
		db = self.gui.library_view.model().db

		paths = []

		for book_id in book_ids:
			mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
			title, formats = mi.title, mi.formats
			for f in formats:
				path = db.format_abspath(book_id, f, index_is_id=True)
				paths.append(path)
		StatusDialog(paths, self.gui).exec_()
				
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
		return 2  # What can we do here???


class StatusDialog(QDialog):

	LONG_TEXT = "Already Exists"

	def __init__(self, paths, parent = None):
		QDialog.__init__(self, parent)
		self.uploaders = []
		self.paths = paths
		self.todo = len(paths)
		self.allowedToClose = False


		self.setWindowTitle("Uploading status")
		layout = QVBoxLayout()
		self.tableWidget = QTableWidget(len(paths), 2, self)
		self.tableWidget.setHorizontalHeaderLabels(("file", "status"))
		for j in xrange(len(self.paths)):
			path = paths[j]
			item = QTableWidgetItem(os.path.basename(path))
			item.setFlags(Qt.NoItemFlags)
			item.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 0, item)
			item = QTableWidgetItem(self.LONG_TEXT)
			item.setFlags(Qt.NoItemFlags)
			item.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 1, item)
		self.tableWidget.verticalHeader().hide()
		self.tableWidget.resizeColumnsToContents()
		layout.addWidget(self.tableWidget)
		box = QDialogButtonBox(QDialogButtonBox.Ok, Qt.Horizontal)
		layout.addWidget(box)
		self.setLayout(layout)
		width = self.width() - self.tableWidget.width() + self.tableWidget.horizontalHeader().length() + 40
		height = self.height() - self.tableWidget.height() + self.tableWidget.verticalHeader().length()  + box.height() + 50
		self.setFixedSize(width, min(height, 400))#FIXME
		for j in xrange(len(self.paths)):
			self.tableWidget.item(j, 1).setText("Uploading")


		self.ok = box.button(QDialogButtonBox.Ok)
		self.ok.setEnabled(False)
		self.ok.clicked.connect(self.close)
		for p in paths:
			uploader = Uploader(p, self)
			self.uploaders.append(uploader)
			uploader.finished.connect(self.onFinished)
			uploader.upload()

	def onFinished(self):
		uploader = self.sender()
		print(uploader.path)
		n = -1
		for i in xrange(len(self.paths)):
			if self.paths[i] == uploader.path:
				n = i
		text = self.tableWidget.item(n, 1).text()
		color = self.tableWidget.item(n, 1).background().color()
		if uploader.status == uploader.Status.uploaded:
			text = "Uploaded"
			color = QColor(127, 255, 127)
		elif uploader.status == uploader.Status.exists:
			text = "Already Exists"
			color = QColor(255, 255, 127)
		elif uploader.status == uploader.Status.error:
			text = "Error"
			color = QColor(255, 127, 127)
		self.tableWidget.item(n, 1).setText(text)
		self.tableWidget.item(n, 1).setBackground(color)
		self.tableWidget.item(n, 0).setBackground(color)
		self.todo -= 1
		if self.todo == 0:
			self.allowedToClose = True
			self.ok.setEnabled(True)

	def closeEvent(self, e):
		if self.allowedToClose:
			QDialog.closeEvent(self, e)
		else:
			e.ignore()

	def reject(self):
		if self.allowedToClose:
			QDialog.reject(self)




class Uploader(QObject):

	finished = pyqtSignal()

	class Status:
		uploaded = 0
		exists = 1
		error = 2
		uploading = 9

	def __init__(self, path, parent=None):
		QObject.__init__(self, parent)
		self.url = BASE_URL + "app/book.upload"
		self.path = path
		self.manager = QNetworkAccessManager(self)
		self.manager.setCookieJar(MyNetworkCookieJar(False, self))
		self.status = self.Status.uploading

	def upload(self):
		self.__check__()

	def __check__(self):
		hasher = hashlib.sha1()
		with open(self.path, 'rb') as afile:
			buf = afile.read(BLOCKSIZE)
			while len(buf) > 0:
				hasher.update(buf)
				buf = afile.read(BLOCKSIZE)
		h = hasher.hexdigest()
		self.referer = BASE_URL + "app/book.status.by.hash?sha1=" + h #FIXME: how to send post + cookies?
		self.request = QNetworkRequest(QUrl(self.referer))
		self.reply = self.manager.get(self.request)
		self.reply.finished.connect(self.__onCheck__)

	def __onCheck__(self):
		if self.sender().error() != 0:
			self.status = self.Status.error
			self.finished.emit()
			return
		try:
			res = json.loads(str(self.sender().readAll()))
			if res["status"] == "found":
				self.status = self.Status.exists
				self.finished.emit()
				return
		except Exception as e:
			self.status = self.Status.error
			self.finished.emit()
			return
		self.csrftoken = None
		for c in self.manager.cookieJar().allCookies():
			if str(c.domain()) == DOMAIN and str(c.name()) == "csrftoken":
				self.csrftoken = str(c.value())
		if not self.csrftoken:
			self.status = self.Status.error
			self.finished.emit()
			return
		self.__upload__()

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
		self.reply.finished.connect(self.__onFinished__)


	def __onFinished__(self):
		if self.sender().error() != 0:
			self.status = self.Status.error
			self.finished.emit()
			return
		self.status = self.Status.uploaded
		self.finished.emit()



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





