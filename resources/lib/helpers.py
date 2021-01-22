# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import requests
import routing
import lookups
import auth
import json
import sys
from string import Template

plugin = routing.Plugin()
addon = xbmcaddon.Addon()

def log(msg, level=1):
	xbmc.log('iPrima: ' + msg, level)

def displayMessage(message, type='INFO'):
	# Possible types: INFO, WARNING, ERROR
	dialog = xbmcgui.Dialog()
	dialog.notification('iPrima', message, getattr(xbmcgui, 'NOTIFICATION_'+type), 5000)

def getResourceUrl(resource, replacements):
	url = lookups.resources[resource]['path']
	if len(replacements) > 0:
		url = url.format(**replacements)
	return url

def getResourceMethod(resource):
	return lookups.resources[resource]['method']

def getResourceContentPath(resource):
	return lookups.resources[resource]['content_path']

def getResourcePostData(resource, options):
	template = Template(lookups.resources[resource]['post_data'])
	return template.substitute(**options)

def getJSONPath(data, keys):
	return getJSONPath(data[keys[0]], keys[1:]) if keys else data

def isPlayable(itemType):
	return lookups.item_types[itemType]['playable']

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


def getAccessToken(refresh=False):
	access_token = xbmcplugin.getSetting(plugin.handle, 'accessToken')
	if not access_token or refresh:
		log('Getting new access token', 2)
		username = xbmcplugin.getSetting(plugin.handle, 'username')
		password = xbmcplugin.getSetting(plugin.handle, 'password')

		access_token = auth.login(username, password)
		addon.setSetting(id='accessToken', value=access_token)
	
	return access_token

def requestResource(resource, count=0, page=0, replace={}, postOptions={}, retrying=False):
	url = getResourceUrl(resource, replace)
	method = getResourceMethod(resource)
	options = {
		'count': str(count or lookups.shared['pagination']),
		'offset': str(page * lookups.shared['pagination'])
	}
	options.update(postOptions)

	token = getAccessToken(refresh=retrying)
	common_headers = {
		'Authorization': 'Bearer ' + token,
		'x-prima-access-token': token,
		'X-OTT-Access-Token': token
	}

	log('Using auth token: ' + token)
	if method == 'POST':
		data = getResourcePostData(resource, options).encode('utf-8')
		contentPath = getResourceContentPath(resource)
		request = postUrl(url, data, common_headers)
	else:
		request = getUrl(url, common_headers)

	log('Response status: ' + str(request.status_code))
	if request.ok:
		return getJSONPath(request.json(), contentPath) if method == 'POST' else request.json()
	elif request.status_code in {401, 403}:
		log('UNAUTHORIZED: ' + request.content)
		if retrying: 
			displayMessage('Chyba autorizace', 'ERROR')
			sys.exit(1)
		return requestResource(resource, count, page, replace, postOptions, retrying=True)

	displayMessage('Server neodpovídá správně', 'ERROR')
	sys.exit(1)

def getUrl(url, headers):
	log('Requesting: ' + url)
	request = requests.get(
		url,
		timeout=20,
		headers=headers
	)
	return request

def postUrl(url, data, headers):
	log('Requesting: %s; with data: %s' % (url, data))
	request = requests.post(
		url,
		data=data,
		timeout=20,
		headers=headers
	)
	return request
