# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from PyQt5.Qt import *

class StatusDialog(QDialog):

	color_lightgood = QColor(192, 255, 192)
	color_darkgood = QColor(0, 80, 0)

	color_lightbad = QColor(255, 192, 192)
	color_darkbad = QColor(80, 0, 0)

	def __init__(self, controller, paths, parent = None):
		QDialog.__init__(self, parent)
		self.uploaders = []
		self.paths = paths
		self.todo = len(paths)
		self.controller = controller
		self.controller.updated.connect(self.onUpdated)
		self.settings = QSettings()
		geom = self.settings.value("StatusDialogGeometry")
		if geom:
			self.restoreGeometry(geom)


		self.setWindowTitle("Uploading status")
		layout = QVBoxLayout()
		self.tableWidget = QTableWidget(len(paths), 3, self)
		self.tableWidget.setHorizontalHeaderLabels(("Upload?","Book", "Status"))
		for j in xrange(len(self.paths)):
			title = paths[j][1]
			cb = QCheckBox()
			cb.setStyleSheet("margin-left:25%; margin-right:25%;")
			item = QTableWidgetItem()
			item.setFlags(Qt.NoItemFlags)
			self.tableWidget.setItem(j, 0, item)
			self.tableWidget.setCellWidget(j, 0, cb)
			item = QTableWidgetItem(title)
			item.setFlags(Qt.NoItemFlags)
			item.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 1, item)
			item = QTableWidgetItem()
			item.setFlags(Qt.NoItemFlags)
			item.setForeground(QColor(0,0,0))
			pb = QProgressBar()
			pb.setMinimum(0)
			pb.setMaximum(100)
			pb.setValue(50)
			p = pb.palette()
			p.setColor(QPalette.Highlight, self.color_darkgood)
			pb.setPalette(p)
			pb.setFormat("Unknown")
			self.tableWidget.setItem(j, 2, item)
			self.tableWidget.setCellWidget(j, 2, pb)
		self.tableWidget.verticalHeader().hide()
		self.tableWidget.resizeColumnsToContents()
		layout.addWidget(self.tableWidget)
		self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.tableWidget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

		buttons = QHBoxLayout()
		self.bstart = QPushButton("Start!")
		self.bclose = QPushButton("Close")
		self.bstart.clicked.connect(self.start)
		self.bclose.clicked.connect(self.close)
		buttons.addWidget(self.bstart)
		buttons.addWidget(self.bclose)
		layout.addLayout(buttons)
		self.setLayout(layout)
		for p in self.paths:
			self.controller.forcecheck(p[0])
		self.update()

	def closeEvent(self, event):
		self.settings.setValue("StatusDialogGeometry", self.saveGeometry())

	def start(self):
		for i in xrange(len(self.paths)):
			p = self.paths[i][0]
			if self.tableWidget.cellWidget(i, 0).isChecked():
				self.tableWidget.cellWidget(i, 0).setChecked(False)
				self.controller.upload(p)

	def update(self):
		inprogress = False
		for i in xrange(len(self.paths)):
			p = self.paths[i][0]
			text = self.tableWidget.item(i, 2).text()
			lightcolor = Qt.white
			darkcolor = self.color_darkgood
			progress = 0
			tooltip = ''
			if p in self.controller.uploaders.keys():
				uploader = self.controller.uploaders[p]
				with uploader.lock:
					if uploader.status.error:
						darkcolor = self.color_darkbad
						lightcolor = self.color_lightbad
						text = "Error"
						progress = 100
						tooltip = uploader.status.error_message
					elif uploader.status.inprocess:
						inprogress = True
						self.tableWidget.cellWidget(i, 0).setEnabled(False)
						self.tableWidget.cellWidget(i, 0).setChecked(False)
						if not uploader.status.exists.known():
							text = "Checking"
						else:
							text = "Uploading"
							progress = uploader.progress
					else:
						self.tableWidget.cellWidget(i, 0).setEnabled(True)
						if uploader.status.uploaded.known():
							if uploader.status.uploaded.value():
								self.tableWidget.cellWidget(i, 0).setEnabled(False)
								self.tableWidget.cellWidget(i, 0).setChecked(False)
								lightcolor = self.color_lightgood
								text = "Uploaded"
								progress = 100
							else:
								darkcolor = self.color_darkbad
								lightcolor = self.color_lightbad
								text = "Error"
						elif uploader.status.exists.known():
							if uploader.status.exists.value():
								self.tableWidget.cellWidget(i, 0).setEnabled(False)
								self.tableWidget.cellWidget(i, 0).setChecked(False)
								lightcolor = self.color_lightgood
								text = "Already Exists"
								progress = 100
							else:
								self.tableWidget.cellWidget(i, 0).setEnabled(True)
								self.tableWidget.cellWidget(i, 0).setChecked(True)
								text = "Ready"
						else:
							text = "Unknown"
			else:
				self.tableWidget.cellWidget(i, 0).setEnabled(True)
				text = "Unknown"
			pb = self.tableWidget.cellWidget(i, 2)
			p = pb.palette()
			p.setColor(QPalette.Highlight, darkcolor)
			pb.setPalette(p)
			pb.setFormat(text)
			pb.setValue(progress)
			pb.setToolTip(tooltip)
			self.tableWidget.item(i, 0).setBackground(lightcolor)
			self.tableWidget.item(i, 1).setBackground(lightcolor)
#		self.bstart.setEnabled(not inprogress)

	def onUpdated(self):
		self.update()
		self.repaint()

