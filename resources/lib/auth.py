# -*- coding: utf-8 -*-

import re
import requests
import sys
import time
import datetime
import random
import math
import routing
import xbmcplugin
import xbmcaddon
import xbmcgui

try:
	from urlparse import urlparse, parse_qs
except ImportError:
	from urllib.parse import urlparse, parse_qs

plugin = routing.Plugin()
addon = xbmcaddon.Addon()

def performCredentialCheck():
	username = xbmcplugin.getSetting(plugin.handle, 'username')
	password = xbmcplugin.getSetting(plugin.handle, 'password')

	if not username or not password:
		registration_notice = xbmcgui.Dialog()
		registration_notice.ok('Nutné přihlášení', 'Pro přehrávání pořadů je nyní potřeba účet na iPrima.cz\n\nPokud účet ještě nemáte, zaregistrujte se na auth.iprima.cz/user/register a v dalším okně vyplňte přihlašovací údaje.')

		username_prompt = xbmcgui.Dialog()
		usr = username_prompt.input('Uživatel (e-mail)')

		if not usr:
			return False
		addon.setSetting(id='username', value=usr)

		password_prompt = xbmcgui.Dialog()
		pswd = password_prompt.input('Heslo', option=xbmcgui.ALPHANUM_HIDE_INPUT)

		if not pswd:
			return False
		addon.setSetting(id='password', value=pswd)

	return True

def generateDeviceId():
	d = (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds() * 1000

	template = 'd-xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
	device_id = ''

	for index, char in enumerate(template):
		if char in {'x', 'y'}:
			r = int( (d + random.random() * 16) % 16 )
			device_id += '{:x}'.format(r) if char == 'x' else '{:x}'.format(r & 0x3 | 0x8)
			d = math.floor(d / 16)
		else:
			device_id += char

	return(device_id)

def getDeviceId():
	from . import helpers
	device_id = xbmcplugin.getSetting(plugin.handle, 'deviceId')

	if not device_id:
		helpers.log('Generating new device id', 2)
		device_id = generateDeviceId()

		addon.setSetting(id='deviceId', value=device_id)

		getAccessToken(refresh=True, device=device_id)

	return device_id

def getAccessToken(refresh=False, device=None):
	from . import helpers

	access_token = xbmcplugin.getSetting(plugin.handle, 'accessToken')
	user_id = xbmcplugin.getSetting(plugin.handle, 'userId')

	if not access_token or refresh:
		helpers.log('Getting new access token', 2)
		username = xbmcplugin.getSetting(plugin.handle, 'username')
		password = xbmcplugin.getSetting(plugin.handle, 'password')
		device_id = device or getDeviceId()

		authentication = login(username, password, device_id)
		access_token = authentication['access_token']
		user_id = authentication['user_uuid']

		addon.setSetting(id='accessToken', value=access_token)
		addon.setSetting(id='userId', value=user_id)

	return {'token': access_token, 'user_id': user_id}

def login(email, password, device_id):
	from . import helpers
	s = requests.Session()

	cookies = {
		'prima_device_id': device_id,
		'from_mobile_app': '1'
	}

	# Get login page
	login_page = s.get('https://auth.iprima.cz/oauth2/login', cookies=cookies)
	login_page_content = login_page.text

	# Acquire CSRF token
	r_csrf = re.search('name="_csrf_token".*value="(.*)"', login_page_content)
	csrf_token = ''
	if r_csrf:
		csrf_token = r_csrf.group(1)
		helpers.log('CSRF: ' + csrf_token)
	else:
		helpers.displayMessage('Nepodařilo se získat CSRF token', 'ERROR')
		sys.exit(1)

	# Log in
	do_login = s.post('https://auth.iprima.cz/oauth2/login', {
		'_email': email,
		'_password': password,
		'_csrf_token': csrf_token
	}, cookies=cookies)
	helpers.log('Auth check URL: ' + do_login.url)

	# Optionally select profile
	profile_id = xbmcplugin.getSetting(plugin.handle, 'profileId')
	if not profile_id:
		profile_id_search = re.search('data-edit-url="/user/profile-edit/(.*)"', do_login.text)
		helpers.log('Selected profile id: {}'.format(profile_id_search[1]))

		if profile_id_search:
			profile_id = profile_id_search[1]
			addon.setSetting(id='profileId', value=profile_id)
		else:
			helpers.displayMessage('Nepodařilo se získat ID profilu', 'ERROR')
			sys.exit(1)

	do_profile_select = s.get(
		'https://auth.iprima.cz/user/profile-select-perform/{}?continueUrl=/oauth2/authorize?response_type=code%26client_id=prima_sso%26redirect_uri=https://auth.iprima.cz/sso/auth-check%26scope=openid%20email%20profile%20phone%20address%20offline_access%26state=prima_sso%26auth_init_url=https://www.iprima.cz/%26auth_return_url=https://www.iprima.cz/?authentication%3Dcancelled'.format(profile_id),
		cookies={
			**cookies,
			'prima_sso_profile': profile_id
		})
	helpers.log('Profile select URL: {}'.format(do_profile_select.url))

	# Acquire authorization code from profile select result
	parsed_auth_url = urlparse(do_profile_select.url)
	try:
		auth_code = parse_qs(parsed_auth_url.query)['code'][0]
	except KeyError:
		helpers.displayMessage('Nepodařilo se získat autorizační kód, zkontrolujte přihlašovací údaje', 'ERROR')
		sys.exit(1)

	# Get access token
	get_token = s.post('https://auth.iprima.cz/oauth2/token', {
		'scope': 'openid+email+profile+phone+address+offline_access',
		'client_id': 'prima_sso',
		'grant_type': 'authorization_code',
		'code': auth_code,
		'redirect_uri': 'https://auth.iprima.cz/sso/auth-check'
	}, cookies=cookies)
	helpers.log('Get token response: ' + get_token.text)

	if get_token.ok:
		return get_token.json()
	else:
		helpers.displayMessage('Nepodařilo se získat access token', 'ERROR')
		sys.exit(1)
