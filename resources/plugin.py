# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import json
import requests
import routing
import sys

from .lib import helpers, lookups, auth

if sys.version_info.major < 3:
	reload(sys)
	sys.setdefaultencoding('utf8')

plugin = routing.Plugin()
addon = xbmcaddon.Addon()

def run():
	lookups.shared['pagination'] = lookups.settings['pagination_options'][int(xbmcplugin.getSetting(plugin.handle, 'pagination'))]

	credentialsAvailable = auth.performCredentialCheck()

	if credentialsAvailable:
		plugin.run()
	else:
		xbmc.executebuiltin("Action(Back,%s)" % xbmcgui.getCurrentWindowId())
		sys.exit(1)


""" 
	ROOT MENU
"""
@plugin.route('/')
def root():
	for item in lookups.menu_items:
		li = xbmcgui.ListItem(item['title'])
		li.setArt( {'icon': item['icon']} )
		url = plugin.url_for_path( '/section/{0}/'.format(item['resource']) )
		
		xbmcplugin.addDirectoryItem(plugin.handle, url, li, isFolder=True)

	settingsItem = xbmcgui.ListItem('Nastavení')
	settingsItem.setArt( {'icon': 'DefaultAddonService.png'} )

	xbmcplugin.addDirectoryItem(plugin.handle, 
		plugin.url_for_path('/action/settings'),
		settingsItem,
		isFolder=True
	)

	xbmcplugin.endOfDirectory(plugin.handle)


""" 
	SECTION LISTING
"""
@plugin.route('/section/<resource>/')
def section(resource):
	page = int(plugin.args['page'][0]) if 'page' in plugin.args else 0
	search = plugin.args['search'][0] if 'search' in plugin.args else ''

	items = helpers.requestResource(resource, page=page, postOptions={'search': search})

	if page == 0 and not search:
		if 'searchable' in lookups.resources[resource]:
			url = plugin.url_for_path( '/action/search/?origin={0}'.format(resource) )
			li = xbmcgui.ListItem('Hledat')
			li.setArt( {'icon': 'DefaultAddonsSearch.png'} )
			xbmcplugin.addDirectoryItem(plugin.handle, url,	li, isFolder=True)

		if 'subsections' in lookups.resources[resource]:
			for item in lookups.resources[resource]['subsections']:
				xbmcplugin.addDirectoryItem(plugin.handle, 
					plugin.url_for_path( '/section/{0}/'.format(item['resource']) ),
					xbmcgui.ListItem(item['title']), 
					isFolder=True
				)

	renderItems(items)
	
	if len(items) == lookups.shared['pagination']:
		xbmcplugin.addDirectoryItem(plugin.handle, 
			plugin.url_for_path( '/section/{0}/?page={1}'.format(resource, page+1) ),
			xbmcgui.ListItem('Další strana'), 
			isFolder=True
		)

	xbmcplugin.endOfDirectory(plugin.handle)


""" 
	PROGRAM LISTING
"""
@plugin.route('/program/<nid>/')
def program(nid):
	page = int(plugin.args['page'][0]) if 'page' in plugin.args else 0
	programDetail = helpers.requestResource( 'program_by_id', page=page, postOptions={'nid': nid} )

	if page == 0:
		for season in programDetail['seasons'] or []:
			li = xbmcgui.ListItem(season)
			url = lookups.shared['plugin_path'] + '/sublisting/{0}/{1}/'.format(nid, season.replace('/', '%2F'))
			xbmcplugin.addDirectoryItem(plugin.handle, url, li, isFolder=True)

		bonuses = helpers.requestResource( 'bonus', postOptions={'programId': nid, 'count': 1} )
		if len(bonuses) > 0:
			li = xbmcgui.ListItem('Bonusy')
			url = plugin.url_for_path( '/sublisting/{0}/bonus/'.format(nid) )
			xbmcplugin.addDirectoryItem(plugin.handle, url, li, isFolder=True)

	renderItems(programDetail['episodes'])

	if len(programDetail['episodes']) == lookups.shared['pagination']:
		xbmcplugin.addDirectoryItem(plugin.handle, 
			plugin.url_for_path( '/program/{0}/?page={1}'.format(nid, page+1) ),
			xbmcgui.ListItem('Další strana'),
			isFolder=True
		)

	xbmcplugin.endOfDirectory(plugin.handle)


""" 
	SUBPROGRAM LISTING
"""
@plugin.route('/sublisting/<programId>/<season>/')
def sublisting(programId, season):
	page = int(plugin.args['page'][0]) if 'page' in plugin.args else 0
	
	if season == 'bonus':
		items = helpers.requestResource( 'bonus', page=page, postOptions={'programId': programId} )
	else:
		items = helpers.requestResource( 'season', page=page, postOptions={'programId': programId, 'season': season.replace('%2F', '/')} )

	renderItems(items)
	
	if len(items) == lookups.shared['pagination']:
		xbmcplugin.addDirectoryItem(plugin.handle, 
			plugin.url_for_path( '/sublisting/{0}/{1}?page={2}'.format(programId, season, page+1) ),
			xbmcgui.ListItem('Další strana'),
			isFolder=True
		)

	xbmcplugin.endOfDirectory(plugin.handle)


""" 
	ITEMS RENDERING
"""
def renderItems(items):
	for item in items:
		if 'admittanceType' in item and item['admittanceType'] not in lookups.free_admittance_types:
			continue

		label = item['name'] if 'name' in item else item['title']
		itemType = item['type'] if 'type' in item else 'video'
		genres = item['genres'] if 'genres' in item else ''
		teaser = item['teaser'] if 'teaser' in item else ''

		isPlayable = helpers.isPlayable(itemType)

		li = xbmcgui.ListItem(label)

		if isPlayable:
			url = plugin.url_for_path( '/action/play/?videoId={0}'.format(item['playId']) )
			li.setProperty('IsPlayable', 'true')
		else:
			url = plugin.url_for_path( '/program/{0}/'.format(item['nid']) )

		infoLabels = {
			'genre': ', '.join( genres or '' ),
			'plot': teaser or ''
		}

		if 'length' in item:
			infoLabels['duration'] = item['length']
		if 'premiereDate' in item:
			infoLabels['premiered'] = item['premiereDate'].split('T')[0]
		if 'thumbnailData' in  item and item['thumbnailData']:
			li.setArt({ 'thumb': item['thumbnailData']['url'] })
		if 'logo' in  item:
			li.setArt({ 'thumb': item['logo'] })

		li.setInfo( type='video', infoLabels=infoLabels )
		xbmcplugin.addDirectoryItem(plugin.handle, url, li, isFolder=not isPlayable)


""" 
	ACTIONS
"""
@plugin.route('/action/<name>')
def action(name):

	if name == 'search':
		keyboard = xbmc.Keyboard('', 'Zadejte název pořadu nebo jeho část:')
		keyboard.doModal()
		if (keyboard.isConfirmed()):
			txt = keyboard.getText()
			origin = plugin.args['origin'][0]
			plugin.args['search'] = [txt]
			section(origin) # cannot use redirect here beacuse of bug in routing module

	if name == 'settings':
		addon.openSettings()

	if name == 'play':
		videoId = plugin.args['videoId'][0]
		videoDetail = helpers.requestResource('play', replace={'id': videoId})
		try:
			url = videoDetail['streamInfos'][0]['url']
		except:
			helpers.displayMessage('Nenalezen žádný stream pro video', 'ERROR')
			return
		li = xbmcgui.ListItem(path=url)

		xbmcplugin.setResolvedUrl(plugin.handle, True, li)
