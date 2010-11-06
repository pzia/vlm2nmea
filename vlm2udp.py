
import urllib2, json, math
import time
import exceptions, threading, socket
from operator import xor

DEBUG=True
WRITE_PAD = 0.001
VLM_PORT = "1010"
VLM_URL = "http://virtual-loup-de-mer.org"
VLM_EMAIL = 'toto@example.com'
VLM_PASSWD = 'yourpass'
VLM_IDU = 13360 #id du bateau
VLM_REFRESH_GPS = 1
VLM_REFRESH_BOATINFO = 45

class VlmUDP:
    "A UDP broadcaster"
    def __init__(self, ipaddr, port):
        self.index = 0
        self.ipaddr = ipaddr
        self.port = port
        self.byname = "udp://" + ipaddr + ":" + port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def feed(self, line):
        "Feed a line from the contents of the GPS log to the daemon."
        if DEBUG :
            print "%s" % line
        self.write(line)
        time.sleep(WRITE_PAD)
        self.index += 1

    def read(self):
        "Discard control strings written by gpsd."
        pass

    def write(self, line):
        self.sock.sendto(line, (self.ipaddr, int(self.port)))

    def drain(self):
        "Wait for the associated device to drain (e.g. before closing)."
        pass	# shutdown() fails on UDP

def millideg2nmea(mdeg, way = 'NS'):
    fdeg = float(mdeg)/1000
    if fdeg > 0 :
        deg = math.floor(fdeg)
        suffix = way[0]
    else :
        deg = math.ceil(fdeg)
        suffix = way[1]
    minutes = (fdeg-deg)*60
    return "%3.4f,%s" % (abs(deg)*100+ abs(minutes), suffix)

def epoc2nmea_time(t):
    return time.strftime('%H%M%S.000', time.gmtime(time.time()))

def epoc2nmea_date(t):
    return time.strftime('%d%m%y', time.gmtime(time.time()))

def nmea_GPGAA(nmea):
    nmeastr = 'GPGAA,'
    nmeastr += "%s,%s,%s,%s,%s,%s,%s" % ( nmea['time'], nmea['latitude'], nmea['longitude'], nmea['type_positionning'],
                                                nmea['nb_satelites'], nmea['HDOP'], nmea['altitude'] )
    nmeastr += nmea['GPGAA_fill']
    return nmeastr2trame(nmeastr)

def nmea_GPRMC(nmea):
    nmeastr = 'GPRMC,'
    nmeastr += "%s,%s,%s,%s,%s,%s,%s" % ( nmea['time'], nmea['state'], nmea['latitude'], nmea['longitude'], nmea['speed'],
                                                nmea['heading'], nmea['date'] )
    nmeastr += nmea['GPRMC_fill']
    return nmeastr2trame(nmeastr)

def nmeastr2trame(nmeastr):
    nmeaord = map(ord, nmeastr)
    checksum = reduce(xor, nmeaord)
    trame = "$" + nmeastr
    if checksum < 16:
       trame += ("*0%X" % checksum)
    else :
       trame += ("*%X" % checksum)
    return trame

def boatinfo2nmea(email, passwd, idu):
    url = "http://virtual-loup-de-mer.org/ws/boatinfo.php?select_idu=%i&forcefmt=json" % idu
    request = urllib2.Request(url)
    request.add_header('User-Agent', 'Mozilla/5.1')

    auth_handler = urllib2.HTTPBasicAuthHandler()
    auth_handler.add_password(realm='VLM Access',
                              uri=url, 
                              user=email,
                              passwd=passwd)

    opener = urllib2.build_opener(auth_handler)
    page = opener.open(request)
    data = page.readlines()
    data = ''.join(data)
    boatinfo = json.loads(data)
    nmea = {}
    nmea['latitude'] = millideg2nmea(boatinfo['LAT'])
    nmea['longitude'] = millideg2nmea(boatinfo['LON'], 'EW')
    nmea['time'] = epoc2nmea_time(boatinfo['LUP'])
    nmea['date'] = epoc2nmea_date(boatinfo['LUP'])
    nmea['nb_satelites'] = '04'
    nmea['type_positionning'] = '1'
    nmea['HDOP'] = '1.0'
    nmea['altitude'] = '10.0,M'
    nmea['GPGAA_fill'] = ',,,,0000'
    nmea['state'] = 'A'
    nmea['speed'] = "%3.2f" % boatinfo['TWS']
    nmea['heading'] = "%3i" % boatinfo['HDG']
    nmea['GPRMC_fill'] = ',,,A'
    
    return nmea


if __name__ == "__main__":
    vu = VlmUDP("127.0.0.1", VLM_PORT)
    lastup = 0.0
    
    while 1:
        if (time.time() - lastup) > VLM_REFRESH_BOATINFO:
            if DEBUG :
                print "GETTING VLM INFO"
            try : 
                nmea = boatinfo2nmea(VLM_EMAIL, VLM_PASSWD, VLM_IDU)
            except :
                continue
            lastup = time.time()
        if DEBUG :
            print "Sending trame"
        vu.feed(nmea_GPGAA(nmea)+"\r\n")
        vu.feed(nmea_GPRMC(nmea)+"\r\n")
        time.sleep(VLM_REFRESH_GPS)
