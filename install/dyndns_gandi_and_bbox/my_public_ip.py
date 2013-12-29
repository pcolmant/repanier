#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, traceback
import telnetlib
import socket
import time
import datetime
import xmlrpclib

HOST = "192.168.1.1"
USER = "admin"
PASSWORD = "$SERIAL_NUMBER_OF_BELGACOM_BBOX2$"

# A récupérer depuis l'interface Gandi
ZONE_ID = $ZONE_ID$
DOMAIN_ID = $DOMAIN_ID$
API_PROD = 'https://rpc.gandi.net/xmlrpc/'
APIKEY_PROD = $APIKEY_PROD$
API_STA = 'https://rpc.ote.gandi.net/xmlrpc/'
APIKEY_STA = $APIKEY_STA$

API = API_PROD
APIKEY = APIKEY_PROD

DOMAIN_NAME = '$REPANIER.BE$'
DNS_RECORD = {'name': '@', 'type': 'A'}
DNS_TTL = 300


def main():
	print datetime.datetime.now().strftime("%Y-%m-%d %H:%M") +" : start"
	exit = False
	error_counter = 0
	while(not(exit) and (error_counter < 5)):
		try:
			tn = telnetlib.Telnet(HOST,23,0.1)
			api = xmlrpclib.ServerProxy(API)
			try:
				tn.read_until("login: ")
				tn.write(USER + "\n")
				tn.read_until("Password: ")
				tn.write(PASSWORD + "\n")
				while(True):
					tn.write("rg_conf_ram_print /dev/ppp0/ip" + "\n")
					tn.read_until("(ip(")
					new_ip = tn.read_until("))")[:-2]
					current_ip = socket.getaddrinfo(DOMAIN_NAME,80)[0][4][0]
					if(new_ip <> None) and (new_ip <> current_ip):
						gandi_ip = api.domain.zone.record.list(APIKEY, ZONE_ID, 0)[0]['value']
						if(gandi_ip <> None) and (new_ip <> gandi_ip):
							print datetime.datetime.now().strftime("%Y-%m-%d %H:%M") +" : old " + gandi_ip + ", new " + new_ip
							# print api.domain.zone.list(APIKEY)
							version_id = api.domain.zone.version.new(APIKEY, ZONE_ID)
							# Mise a jour (suppression puis création de l'enregistrement)
							delete_count = api.domain.zone.record.delete(APIKEY, ZONE_ID, version_id, DNS_RECORD)
							if(delete_count == 0):
								print "no record to delete"
							else:
								DNS_RECORD['value'] = new_ip
								DNS_RECORD['ttl'] = DNS_TTL
								api.domain.zone.record.add(APIKEY, ZONE_ID, version_id, DNS_RECORD)
								# On valide les modifications sur la zone
								api.domain.zone.version.set(APIKEY, ZONE_ID, version_id)
								api.domain.zone.set(APIKEY, DOMAIN_NAME, ZONE_ID)
					time.sleep(2)
			except EOFError:
				error_counter +=1 
				pass
			except socket.timeout:
				error_counter +=1 
				pass
			except socket.error:
				error_counter +=1 
				pass
			tn.write("exit\n")
		except KeyboardInterrupt:
			exit=True
		except:
			error_counter +=1 
			print traceback.format_exc()

if __name__ == '__main__':
	main()