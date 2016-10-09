'''
X-plane NOAA GFS weather plugin.
Copyright (C) 2012-2015 Joan Perez i Cauhe
---
This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or any later version.
'''

from math import hypot, atan2, degrees, exp, log, radians, sin, cos, sqrt, pi
from random import random

class c:
    '''
    Conversion tools
    '''
    #transition references
    transrefs = {}

    randRefs = {}

    @classmethod
    def ms2knots(self, val):
        return val * 1.94384

    @classmethod
    def kel2cel(self, val):
        return val - 273.15

    @classmethod
    def c2p(self, x, y):
        #Cartesian 2 polar conversion
        r = hypot(x, y)
        a = degrees(atan2(x, y))
        if a < 0:
            a += 360
        if a <= 180:
            a = a + 180
        else:
            a = a -180
        return a, r

    @classmethod
    def mb2alt(self, mb):
        altpress = (1 - (mb/1013.25)**0.190284) * 44307
        return altpress

    @classmethod
    def oat2msltemp(self, oat, alt):
        ''' Converts oat temperature to mean sea level.
        oat in C, alt in meters
        http://en.wikipedia.org/wiki/International_Standard_Atmosphere#ICAO_Standard_Atmosphere
        from FL360 (11km) to FL655 (20km) the temperature deviation stays constant at -71.5degreeC
        from MSL up to FL360 (11km) the temperature decreases at a rate of 6.5degreeC/km
        '''
        if alt > 11000:
            return oat + 71.5
        return oat + 0.0065 * alt

    @classmethod
    def greatCircleDistance(self, latlong_a, latlong_b):
        '''Return the great circle distance of 2 coordinatee pairs'''
        EARTH_RADIUS = 6378137

        lat1, lon1 = latlong_a
        lat2, lon2 = latlong_b

        dLat = radians(lat2 - lat1)
        dLon = radians(lon2 - lon1)
        a = (sin(dLat / 2) * sin(dLat / 2) +
        cos(radians(lat1)) * cos(radians(lat2)) *
        sin(dLon / 2) * sin(dLon / 2))
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        d = EARTH_RADIUS * c
        return d

    @classmethod
    def interpolate(self, t1, t2, alt1, alt2, alt):
        if (alt2 - alt1) == 0:
            return t2
        return t1 + (alt - alt1)*(t2 -t1)/(alt2 -alt1)

    @classmethod
    def expoCosineInterpolate(self, t1, t2, alt1, alt2, alt, expo = 3):
        if alt1 == alt2: return t1
        x = (alt - alt1) / float(alt2 - alt1)
        return t1 + (t2 - t1) * x**expo

    @classmethod
    def cosineInterpolate(self, t1, t2, alt1, alt2, alt):
        if alt1 == alt2: return t1
        x = (alt - alt1) / float(alt2 - alt1)
        return t1 + (t2 - t1) * (0.5-cos(pi*x)/2)

    @classmethod
    def cosineInterpolateHeading(self, hdg1, hdg2, alt1, alt2, alt):

        if alt1 == alt2: return hdg1

        t2 = self.shortHdg(hdg1, hdg2)
        t2 = self.cosineInterpolate(0, t2, alt1, alt2, alt)
        t2 += hdg1

        if t2 < 0:
            return t2 + 360
        else:
            return t2 % 360

    @classmethod
    def expoCosineInterpolateHeading(self, hdg1, hdg2, alt1, alt2, alt):

        if alt1 == alt2: return hdg1

        t2 = self.shortHdg(hdg1, hdg2)
        t2 = self.expoCosineInterpolate(0, t2, alt1, alt2, alt)
        t2 += hdg1

        if t2 < 0:
            return t2 + 360
        else:
            return t2 % 360

    @classmethod
    def interpolateHeading(self, hdg1, hdg2, alt1, alt2, alt):
        if alt1 == alt2: return hdg1

        t1 = 0
        t2 = self.shortHdg(hdg1, hdg2)

        t2 =  t1 + (alt - alt1)*(t2 - t1)/(alt2 - alt1)

        t2 += hdg1

        if t2 < 0:
            return t2 + 360
        else:
            return t2 % 360

    @classmethod
    def fog2(self, rh):
        return (80 - rh)/20*24634

    @classmethod
    def toFloat(self, string, default = 0):
        # try to convert to float or return default
        try:
            val = float(string)
        except ValueError:
            val = default
        return val

    @classmethod
    def toInt(self, string, default = 0):
        # try to convert to float or return default
        try:
            val = int(string)
        except ValueError:
            val = default
        return val

    @classmethod
    def rh2visibility(self, rh):
        # http://journals.ametsoc.org/doi/pdf/10.1175/2009JAMC1927.1
        return 1000*(-5.19*10**-10*rh**5.44+40.10)

    @classmethod
    def dewpoint2rh(self, temp, dew):
        return 100*(exp((17.625*dew)/(243.04+dew))/exp((17.625*temp)/(243.04+temp)))

    @classmethod
    def dewpoint(self, temp, rh):
        return 243.04*(log(rh/100)+((17.625*temp)/(243.04+temp)))/(17.625-log(rh/100)-((17.625*temp)/(243.04+temp)))

    @classmethod
    def shortHdg(self, a, b):
        if a == 360: a = 0
        if b == 360: b = 0
        if a > b:
            cw = (360 - a + b)
            ccw = -(a - b);
        else:
            cw = -(360 - b + a)
            ccw = (b - a)
        if abs(cw) < abs(ccw):
            return cw
        return ccw

    @classmethod
    def pa2inhg(self, pa):
        return pa * 0.0002952998016471232

    @classmethod
    def datarefTransition(self, dataref, new, elapsed, speed=0.25, id=False):
        '''
        Dataref time
        '''
        # Save reference to ignore x-plane roundings
        if not id:
            id = str(dataref.DataRef)
        if not id in self.transrefs:
            self.transrefs[id] = dataref.value

        # Return if the value is already set
        if self.transrefs[id] == new:
            return

        current = self.transrefs[id]

        if current > new:
            dir = -1
        else:
            dir = 1
        if abs(current - new) > speed*elapsed + speed:
            new =  current + dir * speed * elapsed

        self.transrefs[id] = new
        dataref.value = new

    @classmethod
    def transition(self, new, id, elapsed, speed=0.25):
        '''Time based transition '''
        if not id in self.transrefs:
            self.transrefs[id] = new
            return new

        current = self.transrefs[id]

        if current > new:
            dir = -1
        else:
            dir = 1
        if abs(current - new) > speed*elapsed + speed:
            new =  current + dir * speed * elapsed

        self.transrefs[id] = new

        return new

    @classmethod
    def transitionClearReferences(self, refs = False, exclude = False):
        ''' Clear transition references '''
        if exclude:
            for ref in self.transrefs.keys():
                if ref.split('-')[0] not in exclude:
                    self.transrefs.pop(ref)
            return

        elif refs:
            for ref in self.transrefs.keys():
                if ref.split('-')[0] in refs:
                    self.transrefs.pop(ref)
        else:
            self.transrefs = {}

    @classmethod
    def transitionHdg(self, new, id, elapsed, speed=0.25):
        '''Time based wind heading transition '''

        if not id in self.transrefs:
            self.transrefs[id] = new
            return new

        current = self.transrefs[id]

        diff = c.shortHdg(current, float(new))

        if abs(diff) < speed*elapsed:
            newval = new
        else:
            if diff > 0:
                diff = 1
            else:
                diff = -1
            newval = current + diff * speed * elapsed
            if newval < 0:
                newval += 360
            else:
                newval %= 360

        self.transrefs[id] = newval
        return newval

    @classmethod
    def datarefTransitionHdg(self, dataref, new, elapsed, vel=1):
        '''
        Time based wind heading transition
        '''
        id = str(dataref.DataRef)
        if not id in self.transrefs:
            self.transrefs[id] = dataref.value

        if self.transrefs[id] == new:
            return

        current = self.transrefs[id]

        diff = c.shortHdg(current, new)
        if abs(diff) < vel*elapsed:
            newval = new
        else:
            if diff > 0:
                diff = +1
            else:
                diff = -1
            newval = current + diff * vel * elapsed
            if newval < 0:
                newval += 360
            else:
                newval %= 360

        self.transrefs[id] = newval
        dataref.value = newval

    @classmethod
    def limit(self, value, max = None, min = None):
        if max is not False and value > max:
            return max
        elif min is not False and value < min:
            return min
        else:
            return value

    @classmethod
    def cc2xp_old(self, cover):
        #Cloud cover to X-plane
        xp = int(cover/100.0*4)
        if xp < 1 and cover > 0:
            xp = 1
        elif cover > 89:
            xp = 4
        return xp

    @classmethod
    def cc2xp(self, cover):
        # GFS Percent cover to XP
        if cover < 1:
            return 0
        if cover < 30:
            return 1 #'FEW'
        if cover < 55:
            return 2 #'SCT'
        if cover < 90:
            return 3 #'BKN'
        return 4 #'OVC'


    @classmethod
    def metar2xpprecipitation(self, kind, intensity, mod, recent):
        ''' Return intensity of a metar precipitation '''

        ints = {'-': 0, '': 1, '+': 2}
        intensity = ints[intensity]

        precipitation, friction = False, False

        precip = {
         'DZ': [0.1, 0.2 , 0.3],
         'RA': [0.3 ,0.5, 0.8],
         'SN': [0.25 ,0.5, 0.8], # Snow
         'SH': [0.7, 0.8,  1]
         }

        wet = {
         'DZ': 1,
         'RA': 1,
         'SN': 2, # Snow
         'SH': 1,
         }

        if mod == 'SH':
            kind = 'SH'

        if kind in precip:
            precipitation = precip[kind][intensity]
        if recent:
            precipitation = 0
        if kind in wet:
            friction = wet[kind]

        return precipitation, friction

    @classmethod
    def strFloat(self, i, false_label = 'na'):
        'Print a float or na if False'
        if i is False:
            return false_label
        else:
            return '%.2f' % (i)
    @classmethod
    def m2ft(cls, n):
        if n is False: return False
        return n * 3.280839895013123

    @classmethod
    def f2m(cls, n):
        if n is False: return False
        return n * 0.3048

    @classmethod
    def sm2m(cls, n):
        if n is False: return False
        return n * 1609.344

    @classmethod
    def m2sm(self, n):
        if n is False: return False
        return n * 0.0006213711922373339

    @classmethod
    def m2kn(cls, n):
        return n * 1852

    @classmethod
    def convertForInput(self, value, conversion, toFloat = False, false_str = 'none'):
        # Make conversion and transform to int
        if value is False:
            value = False
        else:
            convert = getattr(self, conversion)
            value = convert(value)

        if value is False:
            return false_str

        elif not toFloat:
            value = int(value)
        return str(value)

    @classmethod
    def convertFromInput(self, string, conversion, default = False, toFloat = False, max = False, min = False):
        # Convert from str and convert
        value = self.toFloat(string, default)

        if value is False:
            return False

        convert = getattr(self, conversion)
        value = self.limit(convert(value), max, min)

        if toFloat:
            return value
        else:
            return int(round(value))

    @classmethod
    def randPattern(self, id, max_val, elapsed, max_time = 1, min_val = 0, min_time = 1, heading = False):
        ''' Creates random cosine interpolated "patterns" '''

        if id in self.randRefs:
            x1, x2, startime, endtime, time = self.randRefs[id]
        else:
            x1, x2, startime, endtime, time = min_val, 0, 0, 0, 0

        if heading:
            ret =  self.cosineInterpolateHeading(x1, x2, startime, endtime, time)
        else:
            ret =  self.cosineInterpolate(x1, x2, startime, endtime, time)

        time += elapsed

        if time >= endtime:
            # Init randomness
            x2 = min_val + random() * (max_val - min_val)
            t2 = min_time + random() * (max_time - min_time)

            x1 = ret
            startime =  time
            endtime = time + t2

        self.randRefs[id] = x1, x2, startime, endtime, time

        return ret

    @classmethod
    def middleHeading(cls, hd1, hd2):
        if hd2 > hd1:
            return hd1 + (hd2 - hd1)/2
        else:
            return hd2 + (360 + hd1 - hd2)/2
