# all the imports
import os,binascii
from flask import Flask, request, session, g, redirect, url_for, abort, \
		render_template, flash, Blueprint
from flaskext.mysql import MySQL
from flask_mail import Mail,Message
from config import config, ADMINS, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
from werkzeug.utils import secure_filename
from flask import send_from_directory
import datetime, json
from pprint import pprint
from collections import Counter
import re, datetime
import urllib2, urllib
import requests, chartkick
 
import logging
from logging.handlers import SMTPHandler
credentials = None

mysql = MySQL()
# create our little application :)

app = Flask(__name__)

for key in config:
	app.config[key] = config[key]

mail = Mail(app)
# Mail
mail.init_app(app)

if MAIL_USERNAME or MAIL_PASSWORD:
	credentials = (MAIL_USERNAME, MAIL_PASSWORD)
	mail_handler = SMTPHandler((MAIL_SERVER, MAIL_PORT), 'no-reply@' + MAIL_SERVER, ADMINS, 'resetpass', credentials)
	mail_handler.setLevel(logging.ERROR)
	app.logger.addHandler(mail_handler)

mysql.init_app(app)
app.config.from_object(__name__)
ck = Blueprint('ck_page', __name__, static_folder=chartkick.js(), static_url_path='/static')
app.register_blueprint(ck, url_prefix='/ck')
app.jinja_env.add_extension("chartkick.ext.charts")

def tup2float(tup):
	return float('.'.join(str(x) for x in tup))

def get_cursor():
	return mysql.connect().cursor()

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.djt'), 404

@app.route('/about')
def about():
	return render_template('about.djt')

@app.route('/')
def screen():
	return render_template('index.djt')

@app.route('/search', methods=['GET', 'POST'])
def search():
	if request.method == 'POST':
		searchValue = request.form['searchparam']
		params = dict(
			q = searchValue
		)
		url = 'http://localhost:9100/api/search.json'
		resp = requests.get(url=url, params=params)
		data = json.loads(resp.text)
		pprint(data)
		statuses = data["statuses"]
		return render_template('search.djt',tweets=statuses, searchValue=searchValue)
	return render_template('search.djt')

@app.route('/statistics', methods=['GET', 'POST'])
def statistics():
	if request.method == 'POST':
		query = request.form['q']
		sinceDate = request.form['since']
		untilDate = request.form['until']
		print query
		print sinceDate
		print untilDate
		params = dict(
			q = query,
			since = sinceDate,
			until = untilDate,
			source = "cache",
			count = 0,
			field = "mentions,hashtags",
			limit = 100
		)
		url = 'http://localhost:9100/api/search.json'
		resp = requests.get(url=url, params=params)
		data = json.loads(resp.text)
		# aggregationsData = data["aggregations"]
		# mentions = aggregationsData["mentions"]
		# hashtags = aggregationsData["hashtags"]
		statuses = data["statuses"]
		creators = []
		createdTimes = []
		for tweetObject in statuses:
			creators.append(tweetObject["screen_name"])
			createdTimes.append(tweetObject["created_at"])
		creatorsInfo = dict(Counter(creators).iteritems())
		timeInfo = dict(Counter(createdTimes).iteritems())
		creatorJSON = {}
		timeJSON = {}
		for key, value in creatorsInfo.iteritems():
			creatorJSON[str(key)] = value
		for key, value in timeInfo.iteritems():
			timeJSON[str(key)] = value
		return render_template('statistics.djt', creatorJSON=creatorJSON, timeJSON=timeJSON)
	return render_template('statistics.djt')

@app.teardown_appcontext
def close_db(self):
	"""Closes the database again at the end of the request."""
	get_cursor().close()

if __name__ == '__main__':
	app.debug = True
	app.secret_key=os.urandom(24)
	# app.permanent_session_lifetime = datetime.timedelta(seconds=200)
	app.run(host='0.0.0.0', port=8080)