import wx
import urllib2, json, math
import time
import exceptions, threading, socket
import ConfigParser
import os, sys
from operator import xor

DEBUG=False
"""
WRITE_PAD = 0.001
VLM_PORT = "1010"
VLM_URL = "http://virtual-loup-de-mer.org"
VLM_EMAIL = 'YourEmail'
VLM_PASSWD = 'YourPassword'
VLM_IDU = 0000 #id du bateau
VLM_REFRESH_GPS = 5
VLM_REFRESH_BOATINFO = 30
"""

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


class GPSFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, -1, 'VLM2UDP', size=(455, 310),
                          style = wx.CAPTION | wx.SYSTEM_MENU | wx.MINIMIZE_BOX | wx.CLOSE_BOX)
        panel = wx.Panel(self, -1)

        # Choix de VLM_URL
        VlmUrlList = [VLM_URL_01, VLM_URL_02]
        self.VlmUrlLabel = wx.StaticText(panel, -1, "VLM URL:", size = (100, -1))
        self.VlmUrlChoice = wx.ComboBox(panel, -1, VlmUrlList[0],
                                        size = (200, -1),
                                        choices = VlmUrlList,
                                        style = wx.CB_DROPDOWN | wx.CB_READONLY)
        self.Bind(wx.EVT_COMBOBOX, self.OnVlmUrlChoice, self.VlmUrlChoice)

        # Affichage du mail
        self.MailLabel = wx.StaticText(panel, -1, "Mail:", size = (100, -1))
        self.MailText = wx.TextCtrl(panel, -1, VLM_EMAIL,
                                    size = (200, -1),
                                    style = wx.TE_PROCESS_ENTER)
        self.MailText.SetInsertionPoint(0)
        self.MailText.Bind(wx.EVT_TEXT_ENTER, self.EvtMailTextEnter)
        self.MailText.Bind(wx.EVT_TEXT, self.EvtMailText)

        # Affichage du password
        self.PwdLabel = wx.StaticText(panel, -1, "Password:", size = (100, -1))
        self.PwdText = wx.TextCtrl(panel, -1, VLM_PASSWD,
                                   size = (200, -1),
                                   style = wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.Bind(wx.EVT_TEXT_ENTER, self.EvtPwdTextEnter, self.PwdText)
       
        # Choix du boat
        self.BoatsList = ['0 none']
        self.BoatsLabel = wx.StaticText(panel, -1, "Boats:", size = (100, -1))
        self.BoatsChoice = wx.ComboBox(panel, -1, self.BoatsList[0],
                                       size = (200, -1),
                                       choices = self.BoatsList,
                                       style = wx.CB_DROPDOWN | wx.CB_READONLY)
        self.Bind(wx.EVT_COMBOBOX, self.OnBoatsChoice, self.BoatsChoice)
        
        # Les buttons de commande
        self.ButtonGPS = wx.Button(panel, -1, "Start GPS", size = (100, -1))
        self.Bind(wx.EVT_BUTTON, self.OnClickButtonGPS, self.ButtonGPS)
        self.ButtonGPS.SetDefault()
        self.ButtonAction=0

        self.ButtonForce = wx.Button(panel, -1, "Force GPS", size = (100, -1))
        self.Bind(wx.EVT_BUTTON, self.OnClickButtonForce, self.ButtonForce)

        self.ButtonConfig = wx.Button(panel, -1, "Sauvegarde", size = (100, -1))
        self.Bind(wx.EVT_BUTTON, self.OnClickButtonConfig, self.ButtonConfig)

        # Les timers
        self.timer1 = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer1, self.timer1)
        self.timer2 = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer2, self.timer2)

        # La zone Alpha
        self.MultiText = wx.TextCtrl(panel, -1, size = (430, 130), style = wx.TE_MULTILINE | wx.CB_READONLY)

        # Mise en page et affichage
        self.MainSizer = wx.FlexGridSizer(cols = 1, hgap = 6, vgap = 6)
        
        self.UrlSizer = wx.FlexGridSizer(cols = 3, hgap = 6, vgap = 6)
        self.UrlSizer.AddMany([(20, -1), self.VlmUrlLabel, self.VlmUrlChoice])

        self.MailSizer = wx.FlexGridSizer(cols = 3, hgap = 6, vgap = 6)
        self.MailSizer.AddMany([(20, -1), self.MailLabel, self.MailText])

        self.PwdSizer = wx.FlexGridSizer(cols = 3, hgap = 6, vgap = 6)
        self.PwdSizer.AddMany([(20, -1), self.PwdLabel, self.PwdText])
        
        self.BoatSizer = wx.FlexGridSizer(cols = 3, hgap = 6, vgap = 6)
        self.BoatSizer.AddMany([(20, -1), self.BoatsLabel, self.BoatsChoice])

        self.GPSSizer = wx.FlexGridSizer(cols = 4, hgap = 6, vgap = 6)
        self.GPSSizer.AddMany([(20, -1), self.ButtonGPS, self.ButtonForce, self.ButtonConfig])

        self.MultiSizer = wx.FlexGridSizer(cols = 2, hgap = 6, vgap = 6)
        self.MultiSizer.AddMany([(3, -1), self.MultiText])
        
        self.MainSizer.AddMany([(10, -1),
                                self.UrlSizer,
                                self.MailSizer,
                                self.PwdSizer,
                                self.BoatSizer,
                                self.GPSSizer,
                                self.MultiSizer])
        
        panel.SetSizer(self.MainSizer)

        # Message de bienvenue dans la zone Alpha
        self.MultiText.Clear()
        self.MultiText.SetValue("Bienvenue"+"\r\n"+
                                "vlm2udp Ver. 0.2"+"\r\n"+
                                "30/10/2010"+"\r\n"+
                                "By Paparazzia & Stephpen"+"\r\n"+
                                "\r\n"+
                                "Interface GPS entre le site"+"\r\n"+
                                "Virtual Loup de Mer et Maxou"+"\r\n")
        
        # Tentative de recuperation de la liste des bateaux 
        # appartenant au compte (VLM_EMAIL, VLM_PASSWD)
        try:
            self.MultiText.Clear()
            self.BoatFleet = fleet(VLM_EMAIL, VLM_PASSWD)
            self.MyBoats = self.BoatFleet['fleet']
            self.BsBoats = self.BoatFleet['fleet_boatsit']
            self.MyBoatsList = self.MyBoats.keys()
            self.BsBoatsList = self.BsBoats.keys()
            # Recuperation de la liste des boats en course
            self.BoatsList = ExtractBoatsList(self.MyBoats, self.MyBoatsList, self.BsBoats, self.BsBoatsList)
            if self.BoatsList == none:
                self.BoatsList = ['0 none']
  
        except:
            # Sinon, message d'erreur et liste vide
            self.ErrorMailPwd()
            self.BoatsList = ['0 none']

        self.BoatsChoice.Clear()
        self.BoatsChoice.AppendItems(self.BoatsList)
        self.BoatsChoice.SetValue(self.BoatsList[0])

        self.Bind(wx.EVT_CLOSE, self.OnClose)


    def EvtMailTextEnter(self, evt):
        # Validation de l'adresse mail
        global VLM_EMAIL
        global VLM_PASSWD
        global VLM_IDU
        # Recuperation de la valeur des champs mail et password (un appui sur [Enter] valide les deux)
        VLM_EMAIL = self.MailText.GetValue()
        VLM_PASSWD = self.PwdText.GetValue()
        self.StopGPS()

        # Tentative de recuperation de la liste des bateaux 
        # appartenant au compte (VLM_EMAIL, VLM_PASSWD)
        try:
            self.MultiText.Clear()
            self.BoatFleet = fleet(VLM_EMAIL, VLM_PASSWD)
            self.MyBoats = self.BoatFleet['fleet']
            self.BsBoats = self.BoatFleet['fleet_boatsit']
            self.MyBoatsList = self.MyBoats.keys()
            self.BsBoatsList = self.BsBoats.keys()

            self.BoatsList = ExtractBoatsList(self.MyBoats, self.MyBoatsList, self.BsBoats, self.BsBoatsList)
            VLM_IDU = int(self.BoatsList[0][:self.BoatsList[0].find(" ")])

            
        except:
            # Sinon, message d'erreur et liste vide
            self.ErrorMailPwd()
            self.BoatsList = ['0 none']
            VLM_IDU = 0

        # Mise a jour de la liste des bateaux
        self.BoatsChoice.Clear()
        self.BoatsChoice.AppendItems(self.BoatsList)
        self.BoatsChoice.SetValue(self.BoatsList[0])
        
        if DEBUG:
            print "VLM_EMAIL: %s" % VLM_EMAIL
            print "VLM_PASSWD: %s" % VLM_PASSWD
            print "VLM_IDU: %i" % VLM_IDU

        
    def EvtMailText(self, evt):
        if DEBUG:
            print "EVT_TEXT"


    def EvtPwdTextEnter(self, evt):
        # Idem [Validation de l'adresse mail] juste au dessus
        global VLM_EMAIL
        global VLM_PASSWD
        global VLM_IDU
        VLM_EMAIL = self.MailText.GetValue()
        VLM_PASSWD = self.PwdText.GetValue()
        self.StopGPS()

        try:
            self.MultiText.Clear()
            self.BoatFleet = fleet(VLM_EMAIL, VLM_PASSWD)
            self.MyBoats = self.BoatFleet['fleet']
            self.BsBoats = self.BoatFleet['fleet_boatsit']
            self.MyBoatsList = self.MyBoats.keys()
            self.BsBoatsList = self.BsBoats.keys()

            self.BoatsList = ExtractBoatsList(self.MyBoats, self.MyBoatsList, self.BsBoats, self.BsBoatsList)
            VLM_IDU = int(self.BoatsList[0][:self.BoatsList[0].find(" ")])

            
        except:
            self.ErrorMailPwd()
            self.BoatsList = ['0 none']
            VLM_IDU = 0


        self.BoatsChoice.Clear()
        self.BoatsChoice.AppendItems(self.BoatsList)
        self.BoatsChoice.SetValue(self.BoatsList[0])
        
        if DEBUG:
            print "VLM_EMAIL: %s" % VLM_EMAIL
            print "VLM_PASSWD: %s" % VLM_PASSWD
            print "VLM_IDU: %i" % VLM_IDU


    def OnClickButtonGPS(self, event):
        # Activation du GPS en mode AUTO (Avac un bascule sur le button, un coup ON, un coup OFF)
        if self.ButtonAction == 0 and VLM_IDU != 0 :
            self.ButtonGPS.SetLabel("Stop GPS")
            self.ButtonAction=1
            if DEBUG:
                print "VLM_EMAIL: %s" % VLM_EMAIL
                print "VLM_PASSWD: %s" % VLM_PASSWD
                print "VLM_IDU: %i" % VLM_IDU

            # Recuperation des infos sur le site VLM et mise en forme NMEA
            self.nmea = boatinfo2nmea(VLM_EMAIL, VLM_PASSWD, VLM_IDU)
            # Envoi des infos sur le GPS
            vu.feed(nmea_GPGGA(self.nmea)+"\r\n")
            vu.feed(nmea_GPRMC(self.nmea)+"\r\n")
            vu.feed(nmea_xxMWV(self.nmea)+"\r\n")
            vu.feed(nmea_xxVPW(self.nmea)+"\r\n")
            vu.feed(nmea_xxVLW(self.nmea)+"\r\n")
            # Affichage de info dans la zone Alpha
            self.InfoGPS()
            # Demarrage des timers
            # Timer1: envoi les infos sur le GPS toutes les (VLM_REFRESH_GPS*1000) secondes
            # Timer2: recuperation des info VLM toutes les (VLM_REFRESH_BOATINFO*1000) secondes
            self.timer1.Start(VLM_REFRESH_GPS*1000)
            self.timer2.Start(VLM_REFRESH_BOATINFO*1000)
            
        else :
            # Arret du GPS
            self.StopGPS()

        if VLM_IDU == 0:
            # Message d'erreur
            self.ErrorMailPwd()
        
        
    def OnClickButtonForce(self, event):
        # Forcage du GPS
        # On desactive temporairement le GPS AUTO (si actif) 
        GPSActive=0
        if VLM_IDU !=0:
            if self.ButtonAction==1:
                self.StopGPS()
                GPSActive=1
                
            # Changement du label du button le temps de recuperer
            # les infos sur la site VLM
            self.ButtonForce.SetLabel("GPS ...")
            # Recuperation des infos sur le site VLM et mise en forme NMEA
            self.nmea = boatinfo2nmea(VLM_EMAIL, VLM_PASSWD, VLM_IDU)
            # Envoi des infos sur le GPS
            vu.feed(nmea_GPGGA(self.nmea)+"\r\n")
            vu.feed(nmea_GPRMC(self.nmea)+"\r\n")
            vu.feed(nmea_xxMWV(self.nmea)+"\r\n")
            vu.feed(nmea_xxVPW(self.nmea)+"\r\n")
            vu.feed(nmea_xxVLW(self.nmea)+"\r\n")
            # Affichage de info dans la zone Alpha
            self.InfoGPS()
            # On remet le label comme a l'origine
            self.ButtonForce.SetLabel("Force GPS")
            # On reactive le GPS Auto
            if GPSActive==1:
                self.StartGPS()
            
        else:
            # Message d'erreur
            self.ErrorMailPwd()

    def OnClickButtonConfig(self, event):
        # Sauvegarde des parametres dans le fichier de config (vlm2udp.cfg)
        self.ButtonConfig.SetLabel("Save ...")
        
        config = ConfigParser.ConfigParser()

        config.add_section('UserConfig')
        config.set('UserConfig', 'mail', VLM_EMAIL)
        config.set('UserConfig', 'pwd', VLM_PASSWD)
        config.set('UserConfig', 'idu', VLM_IDU)

        config.add_section('VLMConfig')
        config.set('VLMConfig', 'URL_01', VLM_URL_01)
        config.set('VLMConfig', 'URL_02', VLM_URL_02)

        config.add_section('SoftConfig')
        config.set('SoftConfig', 'VLM_PORT', VLM_PORT)
        config.set('SoftConfig', 'VLM_REFRESH_GPS', VLM_REFRESH_GPS)
        config.set('SoftConfig', 'VLM_REFRESH_BOATINFO', VLM_REFRESH_BOATINFO)

        config.write(open('vlm2udp.cfg','w'))
        
        self.ButtonConfig.SetLabel("Sauvegarde")


    def OnTimer1(self, evt):
        # Timer 1 on envoi les infos sur le GPS
        if DEBUG:
            print "Timer1"
        vu.feed(nmea_GPGGA(self.nmea)+"\r\n")
        vu.feed(nmea_GPRMC(self.nmea)+"\r\n")
        vu.feed(nmea_xxMWV(self.nmea)+"\r\n")
        vu.feed(nmea_xxVPW(self.nmea)+"\r\n")
        vu.feed(nmea_xxVLW(self.nmea)+"\r\n")
        # Affichage de info dans la zone Alpha
        self.InfoGPS()
        
        
    def OnTimer2(self, evt):
        # Recuperation des info VLM 
        if DEBUG:
            print "Timer2"
        self.nmea = boatinfo2nmea(VLM_EMAIL, VLM_PASSWD, VLM_IDU)


    def InfoGPS(self):
        # Affichage des info dans la zone Alpha
        t = time.localtime(time.time()) # Recup del'heure system
        st = time.strftime("%H:%M:%S", t) # Mise en forme de l'heure
        # Affichage
        self.MultiText.SetValue(st+"\r\n" +
                                self.BoatsChoice.GetValue()+"\r\n" +
                                nmea_GPGGA(self.nmea)+"\r\n" +
                                nmea_GPRMC(self.nmea)+"\r\n" +
                                nmea_xxMWV(self.nmea)+"\r\n" +
                                nmea_xxVPW(self.nmea)+"\r\n" +
                                nmea_xxVLW(self.nmea)+"\r\n" +
                                "\r\n")
        
    def OnVlmUrlChoice(self, evt):
        # Choix de l'URL
        global VLM_URL
        VLM_URL = self.VlmUrlChoice.GetValue()
        if DEBUG:
            print "VLM_URL: %s" % VLM_URL
            

    def OnBoatsChoice(self, evt):
        # choix du bateau
        global VLM_IDU
        VLM_IDU = int(self.BoatsChoice.GetValue()[:self.BoatsChoice.GetValue().find(" ")])
        
        self.OnClickButtonForce(self)
        
        if DEBUG:
            print "GetValue(): %s" % self.BoatsChoice.GetValue()
            print "GetCurrentSelection(): %i" % self.BoatsChoice.GetCurrentSelection()
            print "VLM_IDU: %i" % VLM_IDU

    def StopGPS(self):
        # Arret du GPS  
        self.ButtonGPS.SetLabel("Start GPS")
        self.ButtonAction=0
        self.timer1.Stop()
        self.timer2.Stop()

    def StartGPS(self):
        # Demmarage du GPS
        self.ButtonGPS.SetLabel("Stop GPS")
        self.ButtonAction=1
        self.timer1.Start(VLM_REFRESH_GPS*1000)
        self.timer2.Start(VLM_REFRESH_BOATINFO*1000)


    def ErrorMailPwd(self):
        # Message d'erreur
        wx.MessageBox("Erreur de Mail ou de password !" + "\r\n" +
                      "Connexion internet defaillante" + "\r\n" +
                      "Aucun bateau en course" + "\r\n",
                      caption="Alerte", style=wx.OK | wx.ICON_ERROR)
        self.MultiText.Clear()
        self.MultiText.SetValue("Veuillez entrer" +"\r\n" +
                                " - Un Mail valide" +"\r\n" +
                                " - Un mot de passe valide" +"\r\n" +
                                " - Verifier votre connexion" +"\r\n" +
                                " - Inscrire un bateau a une course" +"\r\n")
        
    def OnClose(self, evt):
        # Fermuture de l'application
        # Sauvegarde des parametres
        self.OnClickButtonConfig(self)
        # Arret du GPS (Timers)
        if VLM_IDU !=0:
            if self.ButtonAction==1:
                self.StopGPS()
        # Destruction de la fenetre
        self.Destroy()
               
        


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

def nmea_GPGGA(nmea):
    nmeastr = 'GPGGA,'
    nmeastr += "%s,%s,%s,%s,%s,%s,%s" % ( nmea['time'], nmea['latitude'], nmea['longitude'], nmea['type_positionning'],
                                                nmea['nb_satelites'], nmea['HDOP'], nmea['altitude'] )
    nmeastr += nmea['GPGGA_fill']
    return nmeastr2trame(nmeastr)

def nmea_GPRMC(nmea):
    nmeastr = 'GPRMC,'
    nmeastr += "%s,%s,%s,%s,%s,%s,%s" % ( nmea['time'], nmea['state'], nmea['latitude'], nmea['longitude'], nmea['speed'],
                                        nmea['heading'], nmea['date'] )
    nmeastr += nmea['GPRMC_fill']
    return nmeastr2trame(nmeastr)

def nmea_xxMWV(nmea):
    nmeastr = '--MWV,'
    nmeastr += "%s,T,%s,N,%s" % ( nmea['wind_angle'], nmea['wind_speed'], nmea['state'] )
    
    return nmeastr2trame(nmeastr)

def nmea_xxVPW(nmea):
    nmeastr = '--VPW,'
    nmeastr += "%s,N,,M" % ( nmea['VMG'] )
    
    return nmeastr2trame(nmeastr)

def nmea_xxVLW(nmea):
    nmeastr = '--VLW,'
    nmeastr += "%s,N,%s,N" % ( nmea['loch'], nmea['distance_next_WP'] )
    
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
    if DEBUG:
        print boatinfo
    
    nmea = {}
    nmea['latitude'] = millideg2nmea(float(boatinfo['LAT']))
    nmea['longitude'] = millideg2nmea(float(boatinfo['LON']), 'EW')
    nmea['time'] = epoc2nmea_time(boatinfo['LUP'])
    nmea['date'] = epoc2nmea_date(boatinfo['LUP'])
    nmea['nb_satelites'] = '04'
    nmea['type_positionning'] = '1'
    nmea['HDOP'] = '1.0'
    nmea['altitude'] = '10.0,M'
    nmea['GPGGA_fill'] = ',,,,0000'
    nmea['state'] = 'A'
    nmea['speed'] = "%3.2f" % float(boatinfo['BSP'])
    nmea['heading'] = "%3.2f" % float(boatinfo['HDG'])
    nmea['GPRMC_fill'] = ',,,A'
    nmea['wind_angle'] = "%3.2f" % float(boatinfo['TWD'])
    nmea['wind_speed'] = "%3.2f" % float(boatinfo['TWS'])
    nmea['VMG'] = "%3.2f" % float(boatinfo['VMG'])
    nmea['loch'] = "%s" % boatinfo['LOC']
    nmea['distance_next_WP'] = "%3.2f" % float(boatinfo['DNM'])
    
    return nmea

def fleet(email, passwd):
    url = "http://virtual-loup-de-mer.org/ws/playerinfo/fleet_private.php?forcefmt=json"
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
    FleetInfo = json.loads(data)
    
    if DEBUG:
        fleet_perso=FleetInfo['fleet']
        print fleet_perso
        fleet_boatsit=FleetInfo['fleet_boatsit']
    
        i=0
        n_boat=fleet_perso.keys()
    
        print fleet_perso.keys()
        while i < len(n_boat):
            print fleet_perso[fleet_perso.keys()[i]]
            i=i+1

        i=0
        n_boat=fleet_boatsit.keys()
    
        print fleet_boatsit.keys()
        while i < len(n_boat):
            print fleet_boatsit[fleet_boatsit.keys()[i]]
            i=i+1
   
    return FleetInfo

def ExtractBoatsList(MyBoats, MyBoatsList, BsBoats, BsBoatsList):
    My=0
    
    BoatsList = []
    while My < len(MyBoatsList):
        if DEBUG:
            print MyBoats[MyBoatsList[My]]['engaged']
            
        if MyBoats[MyBoatsList[My]]['engaged'] != 0 :
            BoatsList.append("%i %s [Race: %i]" % (MyBoats[MyBoatsList[My]]['idu'],
                                                   MyBoats[MyBoatsList[My]]['boatpseudo'],
                                                   MyBoats[MyBoatsList[My]]['engaged']))
        My = My + 1
            
    Bs=0
    while Bs < len(BsBoatsList):
        if BsBoats[BsBoatsList[Bs]]['engaged'] != 0 :
            BoatsList.append("%i %s [Race: %i]" % (BsBoats[BsBoatsList[Bs]]['idu'],
                                                   BsBoats[BsBoatsList[Bs]]['boatpseudo'],
                                                   BsBoats[BsBoatsList[Bs]]['engaged']))
        Bs = Bs + 1

    if DEBUG:
        print BoatsList
        
    return BoatsList

        



if __name__ == '__main__':
    
    config = ConfigParser.ConfigParser()
    # Test la presence du fichier de config, sinon on le cree
    if os.path.isfile('vlm2udp.cfg') == False :
        config.add_section('UserConfig')
        config.set('UserConfig', 'mail', "email@email.com")
        config.set('UserConfig', 'pwd', "password")
        config.set('UserConfig', 'idu', 0)

        config.add_section('VLMConfig')
        config.set('VLMConfig', 'URL_01', "http://virtual-loup-de-mer.org")
        config.set('VLMConfig', 'URL_02', "http://www.virtual-loup-de-mer.org")

        config.add_section('SoftConfig')
        config.set('SoftConfig', 'VLM_PORT', 1010)
        config.set('SoftConfig', 'VLM_REFRESH_GPS', 3)
        config.set('SoftConfig', 'VLM_REFRESH_BOATINFO', 300)

        config.write(open('vlm2udp.cfg', 'w'))

    # Lecture du fichier de config    
    config.read('vlm2udp.cfg')
    VLM_PORT = config.get('SoftConfig', 'vlm_port')
    VLM_URL = config.get('VLMConfig', 'url_01')
    VLM_URL_01 = config.get('VLMConfig', 'url_01')
    VLM_URL_02 = config.get('VLMConfig', 'url_02')              
    VLM_EMAIL = config.get('UserConfig', 'mail')
    VLM_PASSWD = config.get('UserConfig', 'pwd')
    VLM_IDU = config.getint('UserConfig', 'idu')
    VLM_REFRESH_GPS = config.getint('SoftConfig', 'vlm_refresh_gps')
    VLM_REFRESH_BOATINFO = config.getint('SoftConfig', 'vlm_refresh_boatinfo')
    WRITE_PAD = 0.001
        
    vu = VlmUDP("127.0.0.1", VLM_PORT)
    app = wx.PySimpleApp()        
  
    frame = GPSFrame()
    frame.Show()
    app.MainLoop()
    
    app = None
    vu = None
    config = None



