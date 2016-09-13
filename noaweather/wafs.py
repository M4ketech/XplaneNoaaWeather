'''
X-plane NOAA GFS weather plugin.
Copyright (C) 2012-2015 Joan Perez i Cauhe
---
This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or any later version.
'''

import os
from datetime import datetime, timedelta
import subprocess

from asyncdownload import AsyncDownload
from c import c
from util import util

class WAFS:
    '''
    World Area Forecast System - Upper Air Forecast
    Download and parse functions
    '''
    cycles    = [0, 6, 12, 18]
    forecasts = [6, 9, 12, 15, 18, 21, 24] 
    baseurl = 'http://www.ftp.ncep.noaa.gov/data/nccf/com/gfs/prod'
    
    current_datecycle   = False
    downloading     = False
    
    lastgrib = False
    lastlat, lastlon = False, False
    downloadWait = 0
        
    def __init__(self, conf):
        self.conf        = conf
        self.downloading = False
        
        # Use last grib stored in config if still avaliable
        if self.conf.lastwafsgrib and os.path.exists(os.sep.join([self.conf.cachepath, self.conf.lastwafsgrib])):
            self.lastgrib = self.conf.lastwafsgrib
            self.current_datecycle = self.conf.lastwafsgrib.split(os.sep)[1][:10]
        
    def run(self, lat, lon, rate):
        # Worker thread
        
        datecycle, cycle, forecast = self.getCycleDate()
        
        # Use new grib if dowloaded
        if self.downloading == True:
            if not self.download.q.empty():
                lastgrib = self.download.q.get()
                
                self.downloading = False
                if lastgrib:
                    if not self.conf.keepOldFiles and self.conf.lastwafsgrib:
                        util.remove(os.sep.join([self.conf.cachepath, self.conf.lastwafsgrib]))
                    self.lastgrib = lastgrib
                    self.conf.lastwafsgrib = lastgrib
                    if len(self.conf.lastwafsgrib.split(os.sep)) > 0:
                        self.current_datecycle = self.conf.lastwafsgrib.split(os.sep)[1][:10]
                    else:
                        self.lastgrib = False
                else:
                    # Download fail
                    self.downloadWait = 60
        
        if self.downloadWait > 0:
            self.downloadWait -= rate
        
        # Download new grib if required
        if self.current_datecycle != datecycle and self.conf.download and not self.downloading and self.downloadWait < 1:
            self.downloadCycle(datecycle, cycle, forecast)
            
    def getCycleDate(self):
        '''
        Returns last cycle date avaliable
        '''
        now = datetime.utcnow() 
        # cycle is published with 4 hours 33min delay
        cnow = now - timedelta(hours=5, minutes=0)
        # Get last cycle
        for cycle in self.cycles:
            if cnow.hour >= cycle:
                lcycle = cycle
        # Forecast
        adjs = 0
        if cnow.day != now.day:
            adjs = +24
        # Elapsed from cycle
        forecast = (adjs + now.hour - lcycle)
        # Get current forecast
        for fcast in self.forecasts:
            if forecast <= fcast:
                forecast = fcast
                break

        return ( '%d%02d%02d%02d' % (cnow.year, cnow.month, cnow.day, lcycle), lcycle, forecast)

    def parseGribData(self, filepath, lat, lon):
        '''
        Executes wgrib2 and parses its output
        '''
        args = ['-s',
                '-lon',
                '%f' % (lon),
                '%f' % (lat),
                os.sep.join([self.conf.cachepath, filepath])
                ]
        
        if self.conf.spinfo:
            p = subprocess.Popen([self.conf.wgrib2bin] + args, stdout=subprocess.PIPE, startupinfo=self.conf.spinfo, shell=True)
        else:
            p = subprocess.Popen([self.conf.wgrib2bin] + args, stdout=subprocess.PIPE)
        it = iter(p.stdout)
        
        cat = {}
        for line in it:
            r = line[:-1].split(':')
            # Level, variable, value
            level, variable, value, maxave = [r[4].split(' '),  r[3],  r[7].split(',')[2].split('=')[1], r[6]]
            if len(level) > 1 and level[1] == 'mb' and maxave == 'spatial max':
                #print level[1], variable, value
                alt = int(c.mb2alt(float(level[0])))
                value = float(value)
                if value < 0:
                    value = 0
                if variable == 'CTP':
                    value *= 100
                if variable in ('CAT', 'CTP'):
                    if alt in cat:
                        # override existing value if bigger
                        if value > cat[alt]:
                            cat[alt] = value
                    else:
                        cat[alt] = value
        
        turbulence = []
        for key, value in cat.iteritems():
            turbulence.append([key, value/6.0])
        turbulence.sort()
        
        return turbulence

    def downloadCycle(self, datecycle, cycle, forecast):
        self.downloading = True
        filename = "WAFS_blended_%sf%02d.grib2" % (datecycle, forecast)
        url =  "%s/gfs.%s/%s" % (self.baseurl, datecycle, filename)
        cachefile = os.sep.join(['wafs', '%s_%s' % (datecycle, filename)]) 
        path = os.sep.join([self.conf.cachepath, 'wafs'])
        if not os.path.exists(path):
            os.makedirs(path)
        #print cachefile, url
        self.download = AsyncDownload(self.conf, url, cachefile)
