# all the imports
import os,binascii
from flask import Flask, request, session, g, redirect, url_for, abort, \
		render_template, flash, Blueprint, stream_with_context, Response
from flaskext.mysql import MySQL
from flask_mail import Mail,Message
from config import config, ADMINS, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
from werkzeug.utils import secure_filename
from flask import send_from_directory
import datetime, json
from pprint import pprint
from collections import Counter
from time import sleep
import re, datetime
import urllib2, urllib
import requests, chartkick
from flask_oauthlib.client import OAuth
 
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

oauth = OAuth(app)

from twitter import CONSUMER_KEY, CONSUMER_SECRET

twitter = oauth.remote_app(
	'twitter',
	consumer_key= CONSUMER_KEY,
	consumer_secret= CONSUMER_SECRET,
	base_url='https://api.twitter.com/1.1/',
	request_token_url='https://api.twitter.com/oauth/request_token',
	access_token_url='https://api.twitter.com/oauth/access_token',
	authorize_url='https://api.twitter.com/oauth/authorize',
)


@twitter.tokengetter
def get_twitter_token():
	if 'twitter_oauth' in session:
		resp = session['twitter_oauth']
		return resp['oauth_token'], resp['oauth_token_secret']


@app.before_request
def before_request():
	g.user = None
	if 'twitter_oauth' in session:
		g.user = session['twitter_oauth']
		print g.user

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.djt'), 404

@app.route('/stream')
def streamed_response():
    def generate():
        for i in range(0,50):
        	sleep(2)
        	yield i
    return Response(stream_with_context(generate()))

@app.route('/about')
def about():
	return render_template('about.djt')

@app.route('/')
def screen():
	return render_template('index.djt')

@app.route('/wall', methods=['GET', 'POST'])
def wall():
	if request.method == 'POST':
		searchValue = request.form['query']
		params = dict(
			q = searchValue
		)
		url = 'http://localhost:9100/api/search.json'
		resp = requests.get(url=url, params=params)
		data = json.loads(resp.text)
		pprint(data)
		status = data["statuses"]
		statuses = json.dumps(status)
		return render_template('wall.djt',tweets=statuses, searchValue=searchValue)
	return render_template('wall.djt')

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

@app.route('/twitter')
def index():
	tweets = None
	if g.user is not None:
		resp = twitter.request('statuses/home_timeline.json')
		if resp.status == 200:
			tweets = resp.data
			pprint(tweets)
		else:
			flash('Unable to load tweets from Twitter.')
	return render_template('tweets.djt', tweets=tweets)

@app.route('/tweet', methods=['POST'])
def tweet():
	if g.user is None:
		return redirect(url_for('login', next=request.url))
	status = request.form['tweet']
	if not status:
		return redirect(url_for('index'))
	resp = twitter.post('statuses/update.json', data={
		'status': status
	})
	if resp.status == 403:
		flash('Your tweet was too long.')
	elif resp.status == 401:
		flash('Authorization error with Twitter.')
	else:
		flash('Successfully tweeted your tweet (ID: #%s)' % resp.data['id'])
	return redirect(url_for('index'))


@app.route('/login')
def login():
	callback_url = url_for('oauthorized', next=request.args.get('next'))
	return twitter.authorize(callback=callback_url or request.referrer or None)


@app.route('/logout')
def logout():
	session.pop('twitter_oauth', None)
	return redirect(url_for('index'))


@app.route('/oauthorized')
def oauthorized():
	resp = twitter.authorized_response()
	if resp is None:
		flash('You denied the request to sign in.')
	else:
		session['twitter_oauth'] = resp
	return redirect(url_for('index'))


if __name__ == '__main__':
	app.debug = True
	app.secret_key=os.urandom(24)
	# app.permanent_session_lifetime = datetime.timedelta(seconds=200)
	app.run(host='0.0.0.0', port=8080)