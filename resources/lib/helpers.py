# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import requests
import lookups
import json
import sys
from string import Template

def log(msg, level=1):
	xbmc.log('iPrima: ' + msg, level)

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

def displayMessage(message, type='INFO'):
	# Possible types: INFO, WARNING, ERROR
	dialog = xbmcgui.Dialog()
	dialog.notification('iPrima', message, getattr(xbmcgui, 'NOTIFICATION_'+type), 5000)

def requestResource(resource, count=0, page=0, replace={}, postOptions={}):
	url = getResourceUrl(resource, replace)
	method = getResourceMethod(resource)
	options = {
		'count': str(count or lookups.shared['pagination']),
		'offset': str(page * lookups.shared['pagination'])
	}
	options.update(postOptions)

	if method == 'POST':
		data = getResourcePostData(resource, options).encode('utf-8')
		contentPath = getResourceContentPath(resource)

		log('Requesting: %s; with data: %s' % (url, data))
		request = requests.post(
			url,
			data=data,
			timeout=20
		)
		if request.status_code == requests.codes.ok:
			return getJSONPath(request.json(), contentPath)
	else:
		log('Requesting: ' + url)
		request = requests.get(
			url,
			timeout=20
		)
		if request.status_code == requests.codes.ok:
			return request.json()

	displayMessage('Server neodpovídá správně', 'ERROR')
	sys.exit(1)
