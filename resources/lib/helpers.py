# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import requests
import lookups
import auth
import json
import sys

from string import Template

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

def requestResource(resource, count=0, page=0, replace={}, postOptions={}, retrying=False):
	url = getResourceUrl(resource, replace)
	method = getResourceMethod(resource)
	options = {
		'count': str(count or lookups.shared['pagination']),
		'offset': str(page * lookups.shared['pagination'])
	}
	options.update(postOptions)

	authorization = auth.getAccessToken(refresh=retrying)
	common_headers = {
		'Authorization': 'Bearer ' + authorization['token'],
		'x-prima-access-token': authorization['token'],
		'X-OTT-Access-Token': authorization['token']
	}

	cookies = {
		'prima_device_id': auth.getDeviceId(),
		'prima_sso_logged_in': authorization['user_id']
	}

	log('Using access token: ' + authorization['token'])
	if method == 'POST':
		data = getResourcePostData(resource, options).encode('utf-8')
		contentPath = getResourceContentPath(resource)
		request = postUrl(url, data, common_headers, cookies)
	else:
		request = getUrl(url, common_headers, cookies)

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

def getUrl(url, headers, cookies):
	log('Requesting: ' + url)
	request = requests.get(
		url,
		timeout=20,
		headers=headers,
		cookies=cookies
	)
	return request

def postUrl(url, data, headers, cookies):
	log('Requesting: %s; with data: %s' % (url, data))
	request = requests.post(
		url,
		data=data,
		timeout=20,
		headers=headers,
		cookies=cookies
	)
	return request
