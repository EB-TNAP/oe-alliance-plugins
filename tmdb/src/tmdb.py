#!/usr/bin/env python
# -*- coding: utf-8 -*-
#######################################################################
# maintainer: schomi@vuplus-support.org
#This plugin is free software, you are allowed to
#modify it (if you keep the license),
#but you are not allowed to distribute/publish
#it without source code (this version and your modifications).
#This means you also have to distribute
#source code of your modifications.
#######################################################################

from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.config import *
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText

from Screens.ChoiceBox import ChoiceBox
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.VirtualKeyBoard import VirtualKeyBoard

from Tools.Directories import fileExists

from enigma import eListboxPythonMultiContent, ePicLoad, eServiceCenter, eTimer, gFont, gPixmapPtr, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER

from skin import parameters
import sys
import os
import re
import shutil
import base64
from twisted.web.client import downloadPage
import requests
from PIL import Image

from _thread import start_new_thread


import tmdbsimple as tmdb
from .__init__ import _
from .skins import tmdbScreenSkin, tmdbScreenMovieSkin, tmdbScreenPeopleSkin, tmdbScreenPersonSkin, tmdbScreenSeasonSkin


pname = "TMDb"
pdesc = _("Show movie details from TMDb")
pversion = "1.0.1"
pdate = "20230711"

tmdb.REQUESTS_SESSION = requests.Session()
tmdb.REQUESTS_TIMEOUT = (5, 30)

noCover = "/usr/lib/enigma2/python/Plugins/Extensions/tmdb/pic/no_cover.jpg"
tempDir = "/var/volatile/tmp/tmdb/"

try:
	os.mkdir(tempDir)
except:
	pass


def debug(s, flag="a"):  # pass
	f = open("/usr/lib/enigma2/python/Plugins/Extensions/tmdb/debug.txt", flag)
	f.write(str(s) + '\n')
	f.close()


def asBinary(s):
	try:
		from six import ensure_binary
		return (ensure_binary(s))
	except:
		return s


def cleanFile(text):
	cutlist = ['x264', '720p', '1080p', '1080i', 'PAL', 'GERMAN', 'ENGLiSH', 'WS', 'DVDRiP', 'UNRATED', 'RETAIL', 'Web-DL', 'DL', 'LD', 'MiC', 'MD', 'DVDR', 'BDRiP', 'BLURAY', 'DTS', 'UNCUT', 'ANiME',
				'AC3MD', 'AC3', 'AC3D', 'TS', 'DVDSCR', 'COMPLETE', 'INTERNAL', 'DTSD', 'XViD', 'DIVX', 'DUBBED', 'LINE.DUBBED', 'DD51', 'DVDR9', 'DVDR5', 'h264', 'AVC',
				'WEBHDTVRiP', 'WEBHDRiP', 'WEBRiP', 'WEBHDTV', 'WebHD', 'HDTVRiP', 'HDRiP', 'HDTV', 'ITUNESHD', 'REPACK', 'SYNC']
	text = text.replace('.wmv', '').replace('.flv', '').replace('.ts', '').replace('.m2ts', '').replace('.mkv', '').replace('.avi', '').replace('.mpeg', '').replace('.mpg', '').replace('.iso', '').replace('.mp4', '')

	for word in cutlist:
		text = re.sub('(\_|\-|\.|\+)' + word + '(\_|\-|\.|\+)', '+', text, flags=re.I)
	text = text.replace('.', ' ').replace('-', ' ').replace('_', ' ').replace('+', '').replace(" Director's Cut", "").replace(" director's cut", "").replace("[Uncut]", "").replace("Uncut", "")

	text_split = text.split()
	if text_split and text_split[0].lower() in ("new:", "live:"):
		text_split.pop(0)  # remove annoying prefixes
	text = " ".join(text_split)

	if re.search('[Ss][0-9]+[Ee][0-9]+', text):
		text = re.sub('[Ss][0-9]+[Ee][0-9]+.*[a-zA-Z0-9_]+', '', text, flags=re.S | re.I)
	text = re.sub(r'\(.*\)', '', text).rstrip()  # remove episode number from series, like "series name (234)"

	return text


def cleanEnd(text):
	text = text.replace('.wmv', '').replace('.flv', '').replace('.ts', '').replace('.m2ts', '').replace('.mkv', '').replace('.avi', '').replace('.mpeg', '').replace('.mpg', '').replace('.iso', '').replace('.mp4', '')
	return text


class createList(MenuList):
	def __init__(self):
		MenuList.__init__(self, [], content=eListboxPythonMultiContent)
		font, size = parameters.get("TMDbListFont", ('Regular', 25))
		self.l.setFont(0, gFont(font, size))
		self.l.setItemHeight(30)
		self.l.setBuildFunc(self.buildList)

	def buildList(self, entry):
		width = self.l.getItemSize().width()
		res = [None]
		x, y, w, h = parameters.get("TMDbListName", (5, 1, 1920, 40))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0]))
		return res

	def getCurrent(self):
		cur = self.l.getCurrentSelection()
		return cur and cur[0]


class tmdbConfigScreen(Setup):
	def __init__(self, session):
		Setup.__init__(self, session, "TMDB", plugin="Extensions/tmdb", PluginLanguageDomain="tmdb")
		self.setTitle("TMDb - The Movie Database v" + pversion)


class tmdbScreen(Screen, HelpableScreen):
	skin = tmdbScreenSkin

	def __init__(self, session, service, mode):
		Screen.__init__(self, session)
		tmdb.API_KEY = base64.b64decode('ZDQyZTZiODIwYTE1NDFjYzY5Y2U3ODk2NzFmZWJhMzk=')
		if not config.plugins.tmdb.apiKey.value == "intern":
			tmdb.API_KEY = config.plugins.tmdb.apiKey.value
			print("[TMDb] API Key User: " + str(tmdb.API_KEY))
		self.cert = config.plugins.tmdb.cert.value
		self.mode = mode
		self.saveFilename = ""
		self.piclist = ""
		self.covername = noCover
		self.actcinema = 0
		self.searchtitle = (_("TMDb: ") + _("Results for %s"))
		#self.title = " "
		self.page = 1
		self.id = 1
		if os.path.exists(tempDir) is False:
			os.mkdir(tempDir)

		if self.mode == 1:
			serviceHandler = eServiceCenter.getInstance()
			info = serviceHandler.info(service)
			path = service.getPath()
			self.savePath = path
			self.dir = '/'.join(path.split('/')[:-1]) + '/'
			self.file = self.baseName(path)
			if path.endswith("/") is True:
				path = path[:-1]
				self.file = self.baseName(path)
				self.text = self.baseName(path)
			else:
				self.text = cleanFile(info.getName(service))
				self.saveFilename = path
		else:
			self.text = service
			self.text = cleanFile(service)

		print("[TMDb] Search for" + str(self.text))

		HelpableScreen.__init__(self)
		self["actions"] = HelpableActionMap(self, "TMDbActions",
			{
				"ok": (self.ok, _("Show details")),
				"cancel": (self.cancel, _("Exit")),
				"up": (self.keyUp, _("Selection up")),
				"down": (self.keyDown, _("Selection down")),
				"nextBouquet": (self.chDown, _("Details down")),
				"prevBouquet": (self.chUp, _("Details up")),
				"left": (self.keyLeft, _("Page up")),
				"right": (self.keyRight, _("Page down")),
				"red": (self.cancel, _("Exit")),
				"green": (self.ok, _("Show details")),
				"yellow": (self.searchString, _("Edit search")),
				"blue": (self.menu, _("more ...")),
				"menu": (self.setup, _("Setup")),
				"eventview": (self.searchString, _("Edit search"))
			}, -1)

		self['searchinfo'] = Label(_("TMDb: ") + _("Loading..."))
		self['key_red'] = Label(_("Exit"))
		self['key_green'] = Label(_("Details"))
		self['key_yellow'] = Label(_("Edit search"))
		self['key_blue'] = Label(_("more ..."))
		self["key_menu"] = StaticText(_("MENU"))  # auto menu button
		self['list'] = createList()

		self['cover'] = Pixmap()

		self.onLayoutFinish.append(self.onFinish)

	def onFinish(self):
		if not self.text == "":
			#self.text = self.text.replace("- Director's Cut","").replace("- director's cut","")
			#self.text="xyz123"
			#self.text="Verstehen sie spass"
			#self.text="x-men"
			#self.text="markus lanz"
			#self.text="Live nach Neun"
			#self.text="Two and a half men"
			#self.text="Tatort"
			#self.text="Navy CIS"
			#self.text="Obi wan Kenobi"
			self.timer = eTimer()
			start_new_thread(self.tmdbSearch, ())
		else:
			print("[TMDb] no movie found.")
			self['searchinfo'].setText(_("TMDb: ") + _("No results for %s") % self.text)

	def menu(self):
		options = [
			(_("Exit"), 0),
			(_("Current movies in cinemas"), 1),
			(_("Upcoming movies"), 2),
			(_("Popular movies"), 3),
			(_("Similar movies"), 4),
			(_("Recommendations"), 5),
			(_("Best rated movies"), 6)
		]
		self.session.openWithCallback(self.menuCallback, ChoiceBox, list=options)

	def menuCallback(self, ret):
		self.id = 1
		self.title = " "
		self.page = 1
		self.totalpages = 1
		if ret is not None:
			self.searchtitle = ret[0]
			self.actcinema = ret[1]
		try:
			if self.actcinema in (4, 5):
				self.id = self['list'].getCurrent()[3]
				self.title = self['list'].getCurrent()[0]
		except:
			pass
		start_new_thread(self.tmdbSearch, ())

	def tmdbSearch(self):
		self['searchinfo'].setText(_("TMDb: ") + _("Search for %s ...") % self.text)
		self.lang = config.plugins.tmdb.lang.value
		res = []
		self.count = 0
		json_data = {}
		try:
			if self.actcinema == 1:
				json_data = tmdb.Movies().now_playing(page=self.page, language=self.lang)
			elif self.actcinema == 2:
				json_data = tmdb.Movies().upcoming(page=self.page, language=self.lang)
			elif self.actcinema == 3:
				json_data = tmdb.Movies().popular(page=self.page, language=self.lang)
			elif self.actcinema == 4:
				json_data = tmdb.Movies(self.id).similar_movies(page=self.page, language=self.lang)
			elif self.actcinema == 5:
				json_data = tmdb.Movies(self.id).recommendations(page=self.page, language=self.lang)
			elif self.actcinema == 6:
				json_data = tmdb.Movies().top_rated(page=self.page, language=self.lang)
			else:
				search = tmdb.Search()
				json_data = search.multi(query=self.text, language=self.lang)
			#{u'total_results': 0, u'total_pages': 0, u'page': 1, u'results': []}
			#{u'total_results': 0, u'total_pages': 1, u'page': 1, u'results': []}
			#print"######\n", json_data

			self.totalpages = json_data['total_pages']

			for IDs in json_data['results']:
				self.count += 1
				media = ""
				try:
					media = str(IDs['media_type'])
				except:
					pass
				if self.actcinema >= 1:
					media = "movie"
				id = ""
				try:
					id = str(IDs['id'])
				except:
					pass
				title = ""
				try:
					title = str(IDs['title'])
				except:
					pass
				try:
					title = str(IDs['name'])
				except:
					pass
				date = ""
				try:
					date = ", " + str(IDs['release_date'])[:4]
				except:
					pass
				try:
					date = ", " + str(IDs['first_air_date'])[:4]
				except:
					pass

				if date == ", ":
					date = ""

				if media == "movie":
					mediasubst = _("Movie")
				else:
					mediasubst = _("Series")

				title = "%s (%s%s)" % (title, mediasubst, date)
				coverPath = ""
				try:
					coverPath = str(IDs['poster_path'])
				except:
					pass
				try:
					backdropPath = str(IDs['backdrop_path'])
				except:
					pass

				url_cover = "http://image.tmdb.org/t/p/%s/%s" % (config.plugins.tmdb.themoviedb_coversize.value, coverPath)
				url_backdrop = "http://image.tmdb.org/t/p/%s/%s" % (config.plugins.tmdb.themoviedb_coversize.value, backdropPath)

				if not id == "" or not title == "" or not media == "":
					res.append(((title, url_cover, media, id, url_backdrop),))
			self['list'].setList(res)
			#res.sort() #sorts actual page only
			self.piclist = res
			if self.actcinema >= 1:
				self['searchinfo'].setText(_("TMDb: ") + str(self.searchtitle) + " (" + _("page ") + str(self.page) + "/" + str(self.totalpages) + ") " + str(self.title))
			else:
				self['searchinfo'].setText(_("TMDb: ") + _("Results for %s") % self.text)
			self.getInfo()
			self['list'].pageUp()
		except Exception as e:
			print("[TMDb fetch failure", type(e).__name__, e)
			self['searchinfo'].setText(_("TMDb: ") + _("Server does not respond!"))
			if self.count == 1:
				self['searchinfo'].setText(_("TMDb: ") + _("Results for %s") % self.text)
			if "total_results" not in json_data or json_data['total_results'] == 0:
				self['searchinfo'].setText(_("TMDb: ") + _("No results for %s") % self.text)

	def getInfo(self):
		url_cover = self['list'].getCurrent()[1]
		id = self['list'].getCurrent()[3]

		if url_cover[-4:] == "None":
			self.showCover(noCover)
		else:
			downloadPage(asBinary(url_cover), tempDir + id + ".jpg", timeout=5).addCallback(self.gotData, tempDir + id + ".jpg").addErrback(self.dataError)

	def gotData(self, data, coverSaved):
		self.showCover(coverSaved)

	def dataError(self, error):
		print("[TMDb] Error: %s" % error)

	def showCover(self, coverName):
		if not fileExists(coverName):
			coverName = noCover

		if fileExists(coverName):
			self.picload = ePicLoad()
			self['cover'].instance.setPixmap(gPixmapPtr())
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(coverName, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
			del self.picload
		self.covername = coverName
		# Only one result, launch details
		if config.plugins.tmdb.firsthit.value:
			if self.count == 1:
				self.timer.callback.append(self.ok)
				self.timer.start(1000, False)

	def ok(self):
		self.timer.stop()
		check = self['list'].getCurrent()
		if check is not None:
			# title, url_cover, media, id, url_backdrop
			title = self['list'].getCurrent()[0]
			media = self['list'].getCurrent()[2]
			id = self['list'].getCurrent()[3]
			self.covername = tempDir + id + ".jpg"
			self.url_backdrop = self['list'].getCurrent()[4]
			self.session.open(tmdbScreenMovie, title, media, self.covername, id, self.saveFilename, self.url_backdrop)

	def keyLeft(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].pageUp()
			self.getInfo()

	def keyRight(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].pageDown()
			self.getInfo()

	def keyDown(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].down()
			self.getInfo()

	def keyUp(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].up()
			self.getInfo()

	def chDown(self):
		if self.actcinema >= 1:
			self.page += 1
			if self.page > self.totalpages:
				self.page = 1
			start_new_thread(self.tmdbSearch, ())

	def chUp(self):
		if self.actcinema >= 1:
			self.page -= 1
			if self.page <= 0:
				self.page = 1
			start_new_thread(self.tmdbSearch, ())

	def keyYellow(self):
		return

	def setup(self):
		self.session.open(tmdbConfigScreen)

	def searchString(self):
		self.actcinema = 0
		self.session.openWithCallback(self.goSearch, VirtualKeyBoard, title=(_("Search for Movie:")), text=self.text)

	def goSearch(self, newTitle):
		if newTitle is "" or newTitle is None:
			pass
		else:
			self.text = newTitle
			print("[TMDb] Manual search for: %s" % str(self.text))
			start_new_thread(self.tmdbSearch, ())

	def cancel(self):
		self.delCover()
		self.close()

	def baseName(self, str):
		name = str.split('/')[-1]
		return name

	def delCover(self):
		try:
			shutil.rmtree(tempDir)
		except:
			pass


class tmdbScreenMovie(Screen, HelpableScreen):
	skin = tmdbScreenMovieSkin

	def __init__(self, session, mname, media, coverName, id, saveFilename, url_backdrop):
		Screen.__init__(self, session)
		self.mname = mname
		self.media = media
		if self.media == "movie":
			self.movie = True
		else:
			self.movie = False
		self.coverName = coverName
		self.url_backdrop = url_backdrop
		self.id = id
		self.saveFilename = saveFilename

		HelpableScreen.__init__(self)
		self["actions"] = HelpableActionMap(self, "TMDbActions",
			{
				"ok": (self.ok, _("Crew")),
				"cancel": (self.cancel, _("Exit")),
				"up": (self.keyLeft, _("Selection up")),
				"down": (self.keyRight, _("Selection down")),
				"left": (self.keyLeft, _("Page up")),
				"right": (self.keyRight, _("Page down")),
				"red": (self.cancel, _("Exit")),
				"green": (self.keyGreen, _("Crew")),
				"yellow": (self.keyYellow, _("Seasons")),
				"blue": (self.menu, _("more ...")),
				"menu": (self.setup, _("Setup")),
				"eventview": (self.menu, _("more ..."))
			}, -1)

		self['searchinfo'] = Label(_("TMDb: ") + _("Loading..."))
		self['genre'] = Label("-")
		self['genre_txt'] = Label(_("Genre:"))
		self['description'] = ScrollLabel("")
		self['fulldescription'] = ScrollLabel("")
		self['rating'] = Label("0.0")
		self['votes'] = Label("-")
		self['votes_brackets'] = Label("")
		self['votes_txt'] = Label(_("Votes:"))
		self['runtime'] = Label("-")
		self['runtime_txt'] = Label(_("Runtime:"))
		self['fsk'] = Label("FSK: ?")
		self['subtitle'] = Label("-")
		self['year'] = Label("-")
		self['year_txt'] = Label(_("Year:"))
		self['country'] = Label("-")
		self['country_txt'] = Label(_("Countries:"))
		self['director'] = Label("-")
		self['director_txt'] = Label(_("Director:"))
		self['author'] = Label("-")
		self['author_txt'] = Label(_("Author:"))
		self['studio'] = Label("-")
		self['studio_txt'] = Label(_("Studio:"))
		self['key_red'] = Label(_("Exit"))
		self['key_green'] = Label(_("Crew"))
		self['key_yellow'] = Label(_("Seasons"))
		self['key_blue'] = Label(_("more ..."))
		self["key_menu"] = StaticText(_("MENU"))  # auto menu button
		self['cover'] = Pixmap()
		self['backdrop'] = Pixmap()
		self['fsklogo'] = Pixmap()

		self.onLayoutFinish.append(self.onFinish)

	def onFinish(self):
		if self.movie:
			self['key_yellow'].setText(" ")
		if self.saveFilename == "":
			self['key_blue'].setText(" ")
		# TMDb read
		print("[TMDb] Selected: %s" % self.mname)
		self.showCover(self.coverName)
		self.getBackdrop(self.url_backdrop)
		#self.getData()
		start_new_thread(self.tmdbSearch, ())

	def menu(self):
		if self.saveFilename == "":
			pass
		else:
			options = [
				(_("Save movie description"), 1),
				(_("Delete movie EIT file"), 2),
				(_("Save movie cover"), 3),
				(_("Save movie backdrop"), 4),
				("1+2", 5),
				("1+3", 6),
				("1+2+3", 7),
				("1+2+3+4", 8),
				("3+4", 9)
			]
			self.session.openWithCallback(self.menuCallback, ChoiceBox, list=options)

	def menuCallback(self, ret):
		if ret is None:
			pass
		elif ret[1] == 1:
			self.createTXT()
		elif ret[1] == 2:
			self.deleteEIT()
		elif ret[1] == 3:
			self.saveCover()
		elif ret[1] == 4:
			self.saveBackdrop()
		elif ret[1] == 5:
			self.createTXT()
			self.deleteEIT()
		elif ret[1] == 6:
			self.createTXT()
			self.saveCover()
		elif ret[1] == 7:
			self.createTXT()
			self.deleteEIT()
			self.saveCover()
		elif ret[1] == 8:
			self.createTXT()
			self.deleteEIT()
			self.saveCover()
			self.saveBackdrop()
		elif ret[1] == 9:
			self.saveCover()
			self.saveBackdrop()
		else:
			pass

	def keyLeft(self):
		self['description'].pageUp()
		self['fulldescription'].pageUp()

	def keyRight(self):
		self['description'].pageDown()
		self['fulldescription'].pageDown()

	def tmdbSearch(self):
		self.lang = config.plugins.tmdb.lang.value
		self['searchinfo'].setText(_("TMDb: ") + _("Loading..."))
		print("[TMDb] ID: " + str(self.id))

		try:
			if self.movie:
				json_data = tmdb.Movies(self.id).info(language=self.lang)
				#print json_data
				if json_data['overview'] == "":
					json_data = tmdb.Movies(self.id).info(language="en")
				json_data_cast = tmdb.Movies(self.id).credits(language=self.lang)
				#print json_data_cast
				json_data_fsk = tmdb.Movies(self.id).releases(language=self.lang)
				#print json_data_fsk
			elif not self.movie:
				json_data = tmdb.TV(self.id).info(language=self.lang)
				if json_data['overview'] == "":
					json_data = tmdb.TV(self.id).info(language="en")
				#print json_data
				json_data_cast = tmdb.TV(self.id).credits(language=self.lang)
				#print json_data_cast
				json_data_fsk = tmdb.TV(self.id).content_ratings(language=self.lang)
				#print json_data_fsk
			else:
				return
			self['searchinfo'].setText("%s" % self.mname)
		except:
			self['searchinfo'].setText(_("TMDb: ") + _("No results found, or does not respond!"))
			return

		## Year
		year = ""
		try:
			year = json_data['release_date'][:+4]
			self['year'].setText("%s" % str(year))
		except:
			year = ""

		## Rating
		vote_average = ""
		try:
			vote_average = json_data['vote_average']
			#self['rating'].setText("%s" % str(vote_average))
			self['rating'].setText("%.1f" % vote_average)
		except:
			vote_average = ""

		## Votes
		vote_count = ""
		try:
			vote_count = json_data['vote_count']
			self['votes'].setText("%s" % str(vote_count))
			self['votes_brackets'].setText("(%s)" % str(vote_count))
		except:
			vote_count = ""

		## Runtime
		runtime = ""
		try:
			runtime = json_data['runtime']
			self['runtime'].setText("%s min." % str(runtime))
			runtime = ", " + str(runtime) + " min."
		except:
			runtime = "-"

		## Country
		country_string = ""
		try:
			for country in json_data['production_countries']:
				country_string += country['iso_3166_1'] + "/"
			country_string = country_string[:-1]
			self['country'].setText("%s" % str(country_string))
		except:
			country_string = ""

		## Genre"
		genre_string = ""
		try:
			genre_count = len(json_data['genres'])
			for genre in json_data['genres']:
				genre_string += genre['name'] + ", "
			self['genre'].setText("%s" % str(genre_string[:-2]))
		except:
			genre_string = ""

		## Subtitle
		subtitle = ""
		try:
			subtitle = json_data['tagline']
			if json_data['tagline'] == "":
				subtitle = ""
			else:
				self['subtitle'].setText("%s" % str(subtitle))
				subtitle = str(subtitle) + "\n"
		except:
			subtitle = ""

		## Cast
		cast_string = ""
		try:
			for cast in json_data_cast['cast']:
				cast_string += cast['name'] + " (" + cast['character'] + ")\n"
		except:
			cast_string = ""

		## Crew
		crew_string = ""
		director = ""
		author = ""
		try:
			for crew in json_data_cast['crew']:
				crew_string += crew['name'] + " (" + crew['job'] + ")\n"

				if crew['job'] == "Director":
					director += crew['name'] + ", "
				if crew['job'] == "Screenplay" or crew['job'] == "Writer":
					author += crew['name'] + ", "
			director = director[:-2]
			author = author[:-2]
			self['director'].setText("%s" % str(director))
			self['author'].setText("%s" % str(author))
		except:
			crew_string = ""
			director = ""
			author = ""

		## Studio/Production Company
		studio_string = ""
		try:
			for studio in json_data['production_companies']:
				studio_string += studio['name'] + ", "
			studio_string = studio_string[:-2]
			self['studio'].setText("%s" % str(studio_string))
		except:
			studio_string = ""

		#
		# modify Data for TV/Series
		#
		season = ""
		if not self.movie:
			## Year
			year = ""
			try:
				year = json_data['first_air_date'][:+4]
				self['year'].setText("%s" % str(year))
			except:
				year = ""

			## Country
			country_string = ""
			try:
				for country in json_data['origin_country']:
					country_string += country + "/"
				country_string = country_string[:-1]
				self['country'].setText("%s" % str(country_string))
			except:
				country_string = ""

			## Crew Director
			director = ""
			try:
				for directors in json_data['created_by']:
					director += directors['name'] + ", "
				director = director[:-2]
				self['director'].setText(_("Various"))
				self['author'].setText("%s" % str(director))
			except:
				director = ""

			## Studio/Production Company
			try:
				for studio in json_data['networks']:
					studio_string += studio['name'] + ", "
				studio_string = studio_string[:-2]
				self['studio'].setText("%s" % str(studio_string))
			except:
				studio_string = ""

			## Runtime
			runtime = ""
			try:
				seasons = json_data['number_of_seasons']
				episodes = json_data['number_of_episodes']
				runtime = str(seasons) + " " + _("Seasons") + " / " + str(episodes) + " " + _("Episodes")
				self['runtime'].setText("%s" % runtime)
				runtime = ", " + runtime
			except:
				runtime = ""

			# Series Description
			season = ""
			try:
				for seasons in json_data['seasons']:
					if seasons['season_number'] >= 1:
						season += _("Season") + " " + str(seasons['season_number']) + "/" + str(seasons['episode_count']) + " (" + str(seasons['air_date'])[:4] + ")\n"
			except:
				season = ""

		## Description
		description = ""
		try:
			description = json_data['overview']
			description = description + "\n\n" + cast_string + "\n" + crew_string
			#self['description'].setText("%s" % description.encode('utf_8','ignore'))
			self['description'].setText("%s" % str(description))

			movieinfo = "%s%s %s %s" % (str(genre_string), str(country_string), str(year), str(runtime))
			fulldescription = subtitle + movieinfo + "\n\n" + description + "\n" + season
			#self['fulldescription'].setText("%s" % fulldescription.encode('utf_8','ignore'))
			self['fulldescription'].setText("%s" % str(fulldescription))
			self.text = fulldescription
		except:
			description = "-"

		## FSK
		fsk = "100"
		if self.movie:
			try:
				for country in json_data_fsk['countries']:
					if str(country['iso_3166_1']) == "DE":
						fsk = str(country['certification'])
			except:
				pass
		if not self.movie:
			try:
				for country in json_data_fsk['results']:
					if str(country['iso_3166_1']) == "DE":
						fsk = str(country['rating'])
			except:
				pass

		self.showFSK(fsk)

	def dataError(self, error):
		print("[TMDb] Error: %s" % error)

	def showCover(self, coverName):
		if not fileExists(coverName):
			coverName = noCover

		if fileExists(coverName):
			self.picload = ePicLoad()
			self['cover'].instance.setPixmap(gPixmapPtr())
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(coverName, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
			del self.picload

	def getBackdrop(self, url_backdrop):
		backdropSaved = tempDir + "backdrop.jpg"
		if fileExists(backdropSaved):
			os.remove(backdropSaved)
		if url_backdrop[-4:] == "None":
			print("[TMDb] No backdrop found")
			pass
		else:
			#print"###", url_backdrop
			downloadPage(asBinary(url_backdrop), tempDir + "backdrop.jpg", timeout=5).addCallback(self.gotBackdrop, url_backdrop).addErrback(self.dataError)

	def gotBackdrop(self, res, backdrop):
		#print ("Backdrop download returned", backdrop)
		backdropSaved = tempDir + "backdrop.jpg"
		if not fileExists(backdropSaved):
			pass

		if fileExists(tempDir + "backdrop.jpg"):
			self.picload = ePicLoad()
			self['backdrop'].instance.setPixmap(gPixmapPtr())
			size = self['backdrop'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(backdropSaved, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['backdrop'].instance.setPixmap(ptr)
					self['backdrop'].show()
			del self.picload

	def showFSK(self, fsk):
		self.fsklogo = "/usr/lib/enigma2/python/Plugins/Extensions/tmdb/pic/fsk_" + fsk + ".png"
		self.picload = ePicLoad()
		self['fsklogo'].instance.setPixmap(gPixmapPtr())
		size = self['fsklogo'].instance.size()
		self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
		if self.picload.startDecode(self.fsklogo, 0, 0, False) == 0:
			ptr = self.picload.getData()
			if ptr != None:
				self['fsklogo'].instance.setPixmap(ptr)
				self['fsklogo'].show()
		del self.picload

	def ok(self):
		self.keyGreen()

	def setup(self):
		self.session.open(tmdbConfigScreen)

	def keyYellow(self):
		if not self.movie:
			self.session.open(tmdbScreenSeason, self.mname, self.id, self.media)

	def keyGreen(self):
		self.session.open(tmdbScreenPeople, self.mname, self.id, self.media)

	def cancel(self):
		self.close(True)

	def saveCover(self):
		saveFile = cleanEnd(self.saveFilename)
		if fileExists(self.saveFilename):
			try:
				if not config.plugins.tmdb.coverQuality.value == "original":
					width, height = config.plugins.tmdb.coverQuality.value.split("x", 1)
					img = Image.open(self.coverName)
					img = img.convert('RGBA', colors=256)
					img = img.resize((int(width), int(height)), Image.ANTIALIAS)
					img.save(self.coverName)  # img.save(f, quality=75)

				shutil.copy(self.coverName, saveFile + ".jpg")
				self.session.open(MessageBox, _("Cover saved!"), type=1, timeout=3)
				print("[TMDb] Cover %s.jpg created" % saveFile)
			except:
				print("[TMDb] Error saving cover!")

	def saveBackdrop(self):
		saveFile = cleanEnd(self.saveFilename)
		if fileExists(self.saveFilename):
			try:
				backdropName = tempDir + "backdrop.jpg"
				if not config.plugins.tmdb.backdropQuality.value == "original":
					width, height = config.plugins.tmdb.backdropQuality.value.split("x", 1)
					img = Image.open(backdropName)
					img = img.convert('RGBA', colors=256)
					img = img.resize((int(width), int(height)), Image.ANTIALIAS)
					img.save(backdropName)  # img.save(f, quality=75)

				shutil.copy(backdropName, saveFile + ".bdp.jpg")
				self.session.open(MessageBox, _("Backdrop saved!"), type=1, timeout=3)
				print("[TMDb] Backdrop %s.bdp.jpg created" % saveFile)
			except:
				print("[TMDb] Error saving backdrop!")

	def createTXT(self):
		saveFile = cleanEnd(self.saveFilename)
		if fileExists(self.saveFilename):
			try:
				wFile = open(saveFile + ".txt", "w")
				wFile.write(self.text)
				wFile.close()
				print("[TMDb] %s.txt created" % saveFile)
				self.session.open(MessageBox, _("Movie description saved!"), type=1, timeout=3)
			except:
				print("[TMDb] Error saving TXT file!")

	def deleteEIT(self):
		eitFile = cleanEnd(self.saveFilename) + ".eit"
		try:
			os.remove(eitFile)
			print("[TMDb] %s deleted" % eitFile)
			self.session.open(MessageBox, _("EIT file deleted!"), type=1, timeout=3)
		except:
			print("[TMDb] Error deleting EIT file!")


class tmdbScreenPeople(Screen, HelpableScreen):
	skin = tmdbScreenPeopleSkin

	def __init__(self, session, mname, id, media):
		Screen.__init__(self, session)
		self.mname = mname
		self.id = id
		self.media = media
		if self.media == "movie":
			self.movie = True
		else:
			self.movie = False
		self.covername = noCover

		HelpableScreen.__init__(self)
		self["actions"] = HelpableActionMap(self, "TMDbActions",
			{
				"ok": (self.ok, _("Show details")),
				"cancel": (self.cancel, _("Exit")),
				"up": (self.keyUp, _("Selection up")),
				"down": (self.keyDown, _("Selection down")),
				"up": (self.keyUp, _("Selection up")),
				"nextBouquet": (self.chDown, _("Details down")),
				"prevBouquet": (self.chUp, _("Details up")),
				"right": (self.keyRight, _("Page down")),
				"left": (self.keyLeft, _("Page down")),
				"red": (self.cancel, _("Exit")),
				"green": (self.ok, _("Show details")),
				"blue": (self.keyBlue),
				"menu": (self.keyBlue, _("Setup"))
			}, -1)

		self['searchinfo'] = Label(_("TMDb: ") + _("Loading..."))
		self['data'] = ScrollLabel("")
		self['key_red'] = Label(_("Exit"))
		self['key_green'] = Label(_("Details"))
		self['key_blue'] = Label()
		self["key_menu"] = StaticText(_("MENU"))  # auto menu button
		self['list'] = createList()
		self['cover'] = Pixmap()
		self['backdrop'] = Pixmap()

		self.onLayoutFinish.append(self.onFinish)

	def onFinish(self):
		# TMDb read
		print("[TMDb] Selected: %s" % self.mname)
		self['searchinfo'].setText("%s" % self.mname)
		self.showBackdrop()
		start_new_thread(self.tmdbSearch, ())

	def tmdbSearch(self):
		self.lang = config.plugins.tmdb.lang.value
		self['searchinfo'].setText(_("TMDb: ") + _("Loading..."))
		res = []
		try:
			if self.movie:
				json_data_cast = tmdb.Movies(self.id).credits(language=self.lang)
				#print json_data_cast
			else:
				json_data_cast = tmdb.TV(self.id).credits(language=self.lang)
				#json_data_cast = tmdb.TV_Seasons(self.id,1).credits(language=self.lang)
				json_data_seasons = tmdb.TV(self.id).info(language=self.lang)
				#print json_data_seasons

			for casts in json_data_cast['cast']:
				id = str(casts['id'])
				title = str(casts['name']) + " (" + str(casts['character']) + ")"
				coverPath = str(casts['profile_path'])
				cover = tempDir + id + ".jpg"
				url_cover = "http://image.tmdb.org/t/p/%s/%s" % (config.plugins.tmdb.themoviedb_coversize.value, coverPath)

				if not id == "" or not title == "":
					res.append(((title, url_cover, "", id, None),))

			if not self.movie:
				seasoncnt = 1
				for season in json_data_seasons['seasons']:
					#print"######", season
					seasoncnt = season['season_number']
					#print"#########", str(season['season_number'])
					id = str(season['id'])
					title = str(season['name'])
					date = "(" + str(season['air_date'])[:4] + ")"
					res.append(((title + " " + date, "None", "", None, None),))
					json_data_season = tmdb.TV_Seasons(self.id, seasoncnt).credits(language=self.lang)

					for casts in json_data_season['cast']:
						id = str(casts['id'])
						title = str(casts['name']) + " (" + str(casts['character']) + ")"
						coverPath = str(casts['profile_path'])
						cover = tempDir + id + ".jpg"
						url_cover = "http://image.tmdb.org/t/p/%s/%s" % (config.plugins.tmdb.themoviedb_coversize.value, coverPath)

						if not id == "" or not title == "":
							res.append((("    " + title, url_cover, "", id, None),))

			self['list'].setList(res)
			self.piclist = res
			self.getInfo()
			self['searchinfo'].setText("%s" % self.mname)
		except:
			self['searchinfo'].setText(_("TMDb: ") + _("No results found, or does not respond!"))

	def getInfo(self):
		self['data'].setText("")
		url_cover = self['list'].getCurrent()[1]
		id = self['list'].getCurrent()[3]

		if url_cover[-4:] == "None":
			self.showCover(noCover)
		else:
			if not fileExists(tempDir + id + ".jpg"):
				downloadPage(asBinary(url_cover), tempDir + id + ".jpg", timeout=5).addCallback(self.getData, tempDir + id + ".jpg").addErrback(self.dataError)
			else:
				self.showCover(tempDir + id + ".jpg")

	def getData(self, data, coverSaved):
		self.showCover(coverSaved)

	def dataError(self, error):
		print("[TMDb] Error: %s" % error)

	def showCover(self, coverName):
		self.picload = ePicLoad()
		if not fileExists(coverName):
			coverName = noCover

		if fileExists(coverName):
			self['cover'].instance.setPixmap(gPixmapPtr())
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(coverName, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
			del self.picload
		self.covername = coverName

	def showBackdrop(self):
		backdropSaved = tempDir + "backdrop.jpg"
		if fileExists(backdropSaved):
			self.picload = ePicLoad()
			self['backdrop'].instance.setPixmap(gPixmapPtr())
			size = self['backdrop'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(backdropSaved, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['backdrop'].instance.setPixmap(ptr)
					self['backdrop'].show()
			del self.picload

	def ok(self):
		check = self['list'].getCurrent()
		if check is not None and check[3] is not None:
			id = self['list'].getCurrent()[3]
			self.session.open(tmdbScreenPerson, self.covername, id)

	def keyLeft(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].pageUp()
			self.getInfo()

	def keyRight(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].pageDown()
			self.getInfo()

	def keyDown(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].down()
			self.getInfo()

	def keyUp(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].up()
			self.getInfo()

	def chDown(self):
		self['data'].pageUp()

	def chUp(self):
		self['data'].pageDown()

	def keyBlue(self):
		self.session.open(tmdbConfigScreen)

	def cancel(self):
		self.close()


class tmdbScreenPerson(Screen, HelpableScreen):
	skin = tmdbScreenPersonSkin

	def __init__(self, session, coverName, id):
		Screen.__init__(self, session)
		self.coverName = coverName
		self.id = id

		HelpableScreen.__init__(self)
		self["actions"] = HelpableActionMap(self, "TMDbActions",
			{
				"cancel": (self.cancel, _("Exit")),
				"up": (self.keyLeft, _("Selection up")),
				"down": (self.keyRight, _("Selection down")),
				"left": (self.keyLeft, _("Page up")),
				"right": (self.keyRight, _("Page down")),
				"red": (self.cancel, _("Exit")),
			}, -1)

		self['searchinfo'] = Label(_("TMDb: ") + _("Loading..."))
		self['fulldescription'] = ScrollLabel("")
		self['key_red'] = Label(_("Exit"))
		self['cover'] = Pixmap()
		self['backdrop'] = Pixmap()

		self.onLayoutFinish.append(self.onFinish)

	def onFinish(self):
		self.showBackdrop()
		self.showCover(self.coverName)
		#self.getData()
		start_new_thread(self.tmdbSearch, ())

	def keyLeft(self):
		self['fulldescription'].pageUp()

	def keyRight(self):
		self['fulldescription'].pageDown()

	def tmdbSearch(self):
		self.lang = config.plugins.tmdb.lang.value
		print("[TMDb] ID: ", self.id)
		self['searchinfo'].setText(_("TMDb: ") + _("Loading..."))

		try:
			json_data_person = tmdb.People(self.id).info(language=self.lang)
			#print json_data_person
			self.mname = str(json_data_person['name'])

			## Personal data
			birthday = ""
			try:
				birthday = str(json_data_person['birthday'])
			except:
				birthday = ""

			birthplace = ""
			try:
				birthplace = str(json_data_person['place_of_birth'])
			except:
				birthplace = ""
			gender = ""
			try:
				gender = str(json_data_person['gender'])
				if gender == "1":
					gender = _("female")
				elif gender == "2":
					gender = _("male")
				else:
					gender = _("divers")
			except:
				gender = ""

			## Personal data
			altname = ""
			try:
				altname = "\n" + str(json_data_person['also_known_as'][0]) + ", "
			except:
				altname = ""

			altname1 = ""
			try:
				altname1 = str(json_data_person['also_known_as'][1])
			except:
				altname1 = ""

			rank = ""
			try:
				rank = "\n" + _("Popularity") + ": " + str(json_data_person['popularity'])
			except:
				rank = ""

			biography = ""
			try:
				biography = str(json_data_person['biography'])
				if biography == "":
					json_data_person = tmdb.People(self.id).info(language='en')
					biography = str(json_data_person['biography'])
			except:
				biography = ""

			data = birthday + ", " + birthplace + ", " + gender + altname + altname1 + rank + "\n\n" + biography + "\n\n"

			## Participated data
			#json_data_person = tmdb.People(self.id).combined_credits(language=self.lang)
			json_data_person = tmdb.People(self.id).movie_credits(language=self.lang)
			json_data_person_tv = tmdb.People(self.id).tv_credits(language=self.lang)
			#print str(json_data_person)

			data_movies = []
			# Participated in movies
			try:
				for cast in json_data_person['cast']:
					data_movies.append((cast['release_date']) + " " + str(cast['title']) + "  (" + str(cast['character']) + ")")
			except:
				pass
			# Participated in TV
			try:
				for cast in json_data_person_tv['cast']:
					data_movies.append((cast['first_air_date']) + " " + str(cast['name']) + "  (" + str(cast['character']) + ") - TV")
			except:
				pass

			data_movies.sort(reverse=True)
			cast_movies = ""
			for cast in data_movies:
				cast_movies += cast + '\n'

			data = data + "\n" + _("Known for:") + "\n" + str(cast_movies)
			self['fulldescription'].setText(data)
			self['searchinfo'].setText("%s" % self.mname)
		except:
			self['searchinfo'].setText(_("TMDb: ") + _("No results found, or does not respond!"))

	def showCover(self, coverName):
		self.picload = ePicLoad()
		self['cover'].instance.setPixmap(gPixmapPtr())
		size = self['cover'].instance.size()
		self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
		if self.picload.startDecode(coverName, 0, 0, False) == 0:
			ptr = self.picload.getData()
			if ptr != None:
				self['cover'].instance.setPixmap(ptr)
				self['cover'].show()
		del self.picload

	def showBackdrop(self):
		backdropSaved = tempDir + "backdrop.jpg"
		if fileExists(backdropSaved):
			self.picload = ePicLoad()
			self['backdrop'].instance.setPixmap(gPixmapPtr())
			size = self['backdrop'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(backdropSaved, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['backdrop'].instance.setPixmap(ptr)
					self['backdrop'].show()
			del self.picload

	def ok(self):
		self.cancel()

	def cancel(self):
		self.close(True)


class tmdbScreenSeason(Screen, HelpableScreen):
	skin = tmdbScreenSeasonSkin

	def __init__(self, session, mname, id, media):
		Screen.__init__(self, session)
		self.mname = mname
		self.id = id
		self.media = media
		if self.media == "movie":
			self.movie = True
		else:
			self.movie = False
		self.piclist = ""

		HelpableScreen.__init__(self)
		self["actions"] = HelpableActionMap(self, "TMDbActions",
			{
				"ok": (self.ok, _("Show details")),
				"cancel": (self.cancel, _("Exit")),
				"up": (self.keyUp, _("Selection up")),
				"down": (self.keyDown, _("Selection down")),
				"up": (self.keyUp, _("Selection up")),
				"nextBouquet": (self.chDown, _("Details down")),
				"prevBouquet": (self.chUp, _("Details up")),
				"right": (self.keyRight, _("Page down")),
				"left": (self.keyLeft, _("Page down")),
				"red": (self.cancel, _("Exit")),
				"green": (self.ok, _(" ")),
				"blue": (self.keyBlue),
				"menu": (self.keyBlue, _("Setup"))
			}, -1)

		self['searchinfo'] = Label(_("TMDb: ") + _("Loading..."))
		self['data'] = ScrollLabel("")
		self['key_red'] = Label(_("Exit"))
		self['key_green'] = Label()
		self['key_blue'] = Label()
		self['list'] = createList()

		self['cover'] = Pixmap()
		self['backdrop'] = Pixmap()

		self.onLayoutFinish.append(self.onFinish)

	def onFinish(self):
		# TMDb read
		print("[TMDb] Selected: %s" % self.mname)
		self['searchinfo'].setText("%s" % self.mname)
		self.showBackdrop()
		start_new_thread(self.tmdbSearch, ())

	def tmdbSearch(self):
		self.lang = config.plugins.tmdb.lang.value
		self['searchinfo'].setText(_("TMDb: ") + _("Loading..."))
		res = []
		try:
			# Seasons
			json_data_seasons = tmdb.TV(self.id).info(language=self.lang)
			for seasons in json_data_seasons['seasons']:
				print("[TMDb] Season: %s" % seasons['season_number'])
				id = str(seasons['id'])
				season = seasons['season_number']

				#Episodes
				json_data_episodes = tmdb.TV_Seasons(self.id, season).info(language=self.lang)
				titledate = "(" + str(json_data_episodes['air_date'])[:4] + ")"
				title = str(json_data_episodes['name'])
				title = "%s %s" % (title, titledate)
				overview = str(json_data_episodes['overview'])
				coverPath = str(json_data_episodes['poster_path'])
				cover = tempDir + id + ".jpg"
				url_cover = "http://image.tmdb.org/t/p/%s/%s" % (config.plugins.tmdb.themoviedb_coversize.value, coverPath)
				if not id == "" or not title == "":
					res.append(((title, url_cover, overview, id, None),))

				for names in json_data_episodes['episodes']:
					id = str(names['id'])
					title = str(names['episode_number'])
					name = str(names['name'])
					title = "%+6s %s" % (title, name)
					overview = str(names['overview'])
					coverPath = str(names['still_path'])
					cover = tempDir + id + ".jpg"
					url_cover = "http://image.tmdb.org/t/p/%s/%s" % (config.plugins.tmdb.themoviedb_coversize.value, coverPath)
					if not id == "" or not title == "":
						res.append(((title, url_cover, overview, id, None),))
			self['list'].setList(res)
			self.piclist = res
			self.getInfo()
			self['searchinfo'].setText("%s" % self.mname)
		except:
			self['searchinfo'].setText(_("TMDb: ") + _("No results found, or does not respond!"))

	def getInfo(self):
		self['data'].setText("...")
		url_cover = self['list'].getCurrent()[1]
		id = self['list'].getCurrent()[3]

		if url_cover[-4:] == "None":
			self.showCover(noCover)
		else:
			if not fileExists(tempDir + id + ".jpg"):
				downloadPage(asBinary(url_cover), tempDir + id + ".jpg", timeout=5).addCallback(self.getData, tempDir + id + ".jpg").addErrback(self.dataError)
			else:
				self.showCover(tempDir + id + ".jpg")

	def getData(self, data, coverSaved):
		self.showCover(coverSaved)

	def dataError(self, error):
		print("[TMDb] Error: %s" % error)

	def showCover(self, coverName):
		self.picload = ePicLoad()
		if not fileExists(coverName):
			coverName = noCover

		if fileExists(coverName):
			self['cover'].instance.setPixmap(gPixmapPtr())
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(coverName, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
			del self.picload
		self.ok()  # Shortcut

	def showBackdrop(self):
		backdropSaved = tempDir + "backdrop.jpg"
		if fileExists(backdropSaved):
			self.picload = ePicLoad()
			self['backdrop'].instance.setPixmap(gPixmapPtr())
			size = self['backdrop'].instance.size()
			self.picload.setPara((size.width(), size.height(), 1, 1, False, 1, ""))
			if self.picload.startDecode(backdropSaved, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['backdrop'].instance.setPixmap(ptr)
					self['backdrop'].show()
			del self.picload

	def ok(self):
		check = self['list'].getCurrent()
		if check is not None:
			data = self['list'].getCurrent()[2]
			self['data'].setText(data)

	def keyLeft(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].pageUp()
			self.getInfo()

	def keyRight(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].pageDown()
			self.getInfo()

	def keyDown(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].down()
			self.getInfo()

	def keyUp(self):
		check = self['list'].getCurrent()
		if check is not None:
			self['list'].up()
			self.getInfo()

	def chDown(self):
		self['data'].pageUp()

	def chUp(self):
		self['data'].pageDown()

	def keyBlue(self):
		self.session.open(tmdbConfigScreen)

	def cancel(self):
		self.close()
